package main

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"brainchain/cmd/chat/internal/adapter"

	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

var (
	bgPanel         = lipgloss.Color("#1a1a1a")
	textColor       = lipgloss.Color("#e0e0e0")
	textMuted       = lipgloss.Color("#6b6b6b")
	accentColor     = lipgloss.Color("#fab283")
	userBorder      = lipgloss.Color("#7aa2f7")
	assistantBorder = lipgloss.Color("#fab283")
)

type chatMessage struct {
	role    string
	content string
	time    time.Time
}

type tuiModel struct {
	viewport    viewport.Model
	input       textinput.Model
	messages    []chatMessage
	width       int
	height      int
	ready       bool
	showWelcome bool
	adapter     adapter.Adapter
	streaming   bool
}

func newTUIModel() tuiModel {
	ti := textinput.New()
	ti.Placeholder = "메시지를 입력하세요..."
	ti.Focus()
	ti.CharLimit = 4096
	ti.Width = 80

	ti.PromptStyle = lipgloss.NewStyle().Foreground(accentColor).Bold(true)
	ti.TextStyle = lipgloss.NewStyle().Foreground(textColor)
	ti.PlaceholderStyle = lipgloss.NewStyle().Foreground(textMuted)
	ti.Prompt = "> "

	return tuiModel{
		input:       ti,
		messages:    []chatMessage{},
		showWelcome: true,
		adapter:     adapter.GetAvailable(),
	}
}

type streamChunkMsg string
type streamErrorMsg string

func (m tuiModel) Init() tea.Cmd {
	return textinput.Blink
}

func (m *tuiModel) sendMessage(input string) tea.Cmd {
	return func() tea.Msg {
		if m.adapter == nil {
			return streamErrorMsg("CLI를 찾을 수 없습니다. claude 또는 codex를 설치하세요")
		}

		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
		defer cancel()

		result, err := m.adapter.Run(ctx, input, "", nil)
		if err != nil {
			return streamErrorMsg(err.Error())
		}

		if !result.Success {
			if result.Error != "" {
				return streamErrorMsg(result.Error)
			}
			return streamErrorMsg("Command failed")
		}

		return streamChunkMsg(result.Output)
	}
}

func (m tuiModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var (
		tiCmd tea.Cmd
		vpCmd tea.Cmd
	)

	m.input, tiCmd = m.input.Update(msg)
	m.viewport, vpCmd = m.viewport.Update(msg)

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

		headerHeight := 1
		footerHeight := 1
		inputHeight := 3
		viewportHeight := m.height - headerHeight - footerHeight - inputHeight

		if !m.ready {
			m.viewport = viewport.New(m.width, viewportHeight)
			m.viewport.SetContent(m.renderContent())
			m.ready = true
		} else {
			m.viewport.Width = m.width
			m.viewport.Height = viewportHeight
		}

		m.input.Width = m.width - 8

	case tea.KeyMsg:
		switch msg.Type {
		case tea.KeyCtrlC, tea.KeyEsc:
			return m, tea.Quit

		case tea.KeyEnter:
			input := strings.TrimSpace(m.input.Value())
			if input != "" && !m.streaming {
				m.showWelcome = false
				m.streaming = true

				m.messages = append(m.messages, chatMessage{
					role:    "user",
					content: input,
					time:    time.Now(),
				})

				m.messages = append(m.messages, chatMessage{
					role:    "assistant",
					content: "생각 중...",
					time:    time.Now(),
				})

				m.input.Reset()
				m.viewport.SetContent(m.renderContent())
				m.viewport.GotoBottom()

				return m, m.sendMessage(input)
			}
		}

	case streamChunkMsg:
		m.streaming = false
		if len(m.messages) > 0 && m.messages[len(m.messages)-1].role == "assistant" {
			m.messages[len(m.messages)-1].content = string(msg)
		}
		m.viewport.SetContent(m.renderContent())
		m.viewport.GotoBottom()
		return m, nil

	case streamErrorMsg:
		m.streaming = false
		if len(m.messages) > 0 && m.messages[len(m.messages)-1].role == "assistant" {
			m.messages[len(m.messages)-1].content = "오류: " + string(msg)
		}
		m.viewport.SetContent(m.renderContent())
		m.viewport.GotoBottom()
		return m, nil
	}

	return m, tea.Batch(tiCmd, vpCmd)
}

func (m tuiModel) renderContent() string {
	if m.showWelcome {
		return m.renderWelcome()
	}
	return m.renderMessages()
}

func (m tuiModel) renderWelcome() string {
	logoStyle := lipgloss.NewStyle().Foreground(accentColor)

	logo := logoStyle.Render(`
 ██████╗ ██████╗  █████╗ ██╗███╗   ██╗ ██████╗██╗  ██╗ █████╗ ██╗███╗   ██╗
 ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║██╔════╝██║  ██║██╔══██╗██║████╗  ██║
 ██████╔╝██████╔╝███████║██║██╔██╗ ██║██║     ███████║███████║██║██╔██╗ ██║
 ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║██║     ██╔══██║██╔══██║██║██║╚██╗██║
 ██████╔╝██║  ██║██║  ██║██║██║ ╚████║╚██████╗██║  ██║██║  ██║██║██║ ╚████║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝
`)

	subtitleStyle := lipgloss.NewStyle().Foreground(textMuted)

	providerInfo := "프로바이더를 찾을 수 없습니다"
	if m.adapter != nil {
		providerInfo = "사용 중: " + m.adapter.DisplayName()
	}
	subtitle := subtitleStyle.Render(providerInfo)

	helpStyle := lipgloss.NewStyle().Foreground(textMuted).MarginTop(2)

	help := helpStyle.Render("메시지를 입력하고 Enter를 누르세요 • Ctrl+C로 종료")

	content := lipgloss.JoinVertical(lipgloss.Center, logo, subtitle, help)

	return lipgloss.Place(m.width, m.viewport.Height, lipgloss.Center, lipgloss.Center, content)
}

func (m tuiModel) renderMessages() string {
	var sb strings.Builder

	for i, msg := range m.messages {
		var borderCol lipgloss.Color
		var roleLabel string

		if msg.role == "user" {
			borderCol = userBorder
			roleLabel = "나"
		} else {
			borderCol = assistantBorder
			roleLabel = "AI"
		}

		panelStyle := lipgloss.NewStyle().
			Background(bgPanel).
			Padding(1, 2).
			BorderLeft(true).
			BorderStyle(lipgloss.ThickBorder()).
			BorderForeground(borderCol).
			Width(m.width - 4)

		roleStyle := lipgloss.NewStyle().Foreground(textMuted).MarginBottom(0)
		contentStyle := lipgloss.NewStyle().Foreground(textColor)

		roleText := roleStyle.Render(roleLabel)
		contentText := contentStyle.Render(msg.content)

		panel := panelStyle.Render(roleText + "\n" + contentText)

		if i > 0 {
			sb.WriteString("\n")
		}
		sb.WriteString(panel)
	}

	return sb.String()
}

func (m tuiModel) View() string {
	if !m.ready {
		return "초기화 중..."
	}

	headerStyle := lipgloss.NewStyle().Foreground(accentColor).Bold(true).Padding(0, 1)
	header := headerStyle.Render("⌬ brainchain")

	statusStyle := lipgloss.NewStyle().Foreground(textMuted).Padding(0, 1)
	providerName := "none"
	if m.adapter != nil {
		providerName = m.adapter.Name()
	}
	status := statusStyle.Render(fmt.Sprintf("%s • %d개 메시지", providerName, len(m.messages)))

	headerLine := lipgloss.JoinHorizontal(lipgloss.Top,
		header,
		lipgloss.NewStyle().Width(m.width-lipgloss.Width(header)-lipgloss.Width(status)).Render(""),
		status,
	)

	inputBoxStyle := lipgloss.NewStyle().Background(bgPanel).Padding(1, 1).Width(m.width)
	inputArea := inputBoxStyle.Render(m.input.View())

	footerStyle := lipgloss.NewStyle().Foreground(textMuted).Padding(0, 1)
	cwd, _ := os.Getwd()
	footer := footerStyle.Render(cwd)

	return lipgloss.JoinVertical(lipgloss.Left, headerLine, m.viewport.View(), inputArea, footer)
}

func runTUI() error {
	p := tea.NewProgram(
		newTUIModel(),
		tea.WithAltScreen(),
	)

	_, err := p.Run()
	return err
}
