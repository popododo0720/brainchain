package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"brainchain/cmd/chat/internal/config"
	"brainchain/cmd/chat/internal/sdk"

	"github.com/charmbracelet/bubbles/spinner"
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
	thinkingColor   = lipgloss.Color("#9ece6a")
	toolColor       = lipgloss.Color("#bb9af7")
)

type messageType int

const (
	msgUser messageType = iota
	msgAssistant
	msgThinking
	msgTool
)

type chatMessage struct {
	msgType  messageType
	content  string
	toolName string
	time     time.Time
}

type tuiModel struct {
	viewport       viewport.Model
	input          textinput.Model
	spinner        spinner.Model
	messages       []chatMessage
	currentOutput  strings.Builder
	width          int
	height         int
	ready          bool
	showWelcome    bool
	streaming      bool
	status         string
	cmd            *exec.Cmd
	sessionID      string
	bridge         *sdk.Bridge
	useSDK         bool
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

	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(accentColor)

	m := tuiModel{
		input:       ti,
		spinner:     s,
		messages:    []chatMessage{},
		showWelcome: true,
		status:      "ready",
		useSDK:      false,
	}

	cfg, err := config.Load("")
	if err == nil {
		prompts, err := config.LoadPrompts(cfg, "")
		if err == nil {
			bridge, err := sdk.NewBridge(cfg, prompts)
			if err == nil {
				m.bridge = bridge
				m.useSDK = true
			}
		}
	}

	return m
}

type streamEvent struct {
	EventType string
	Content   string
	ToolName  string
	Done      bool
	Error     string
	SessionID string
}

func (m tuiModel) Init() tea.Cmd {
	return tea.Batch(textinput.Blink, m.spinner.Tick)
}

func streamWithSDK(bridge *sdk.Bridge, prompt string, sessionID string) tea.Cmd {
	return func() tea.Msg {
		eventCh := make(chan sdk.Event, 100)
		
		go func() {
			bridge.Chat(prompt, sessionID, eventCh)
			close(eventCh)
		}()

		var result strings.Builder
		var thinking strings.Builder
		var reasoning strings.Builder
		var tools []string
		var capturedSessionID string

		for event := range eventCh {
			switch event.Type {
			case sdk.EventSystem:
				if event.SessionID != "" {
					capturedSessionID = event.SessionID
				}
			case sdk.EventThinking:
				thinking.Reset()
				thinking.WriteString(event.Content)
			case sdk.EventReasoning:
				reasoning.Reset()
				reasoning.WriteString(event.Content)
			case sdk.EventText:
				result.Reset()
				result.WriteString(event.Content)
			case sdk.EventToolStart:
				tools = append(tools, event.Name)
			case sdk.EventResult:
				if event.SessionID != "" {
					capturedSessionID = event.SessionID
				}
			case sdk.EventError:
				return streamEvent{EventType: "error", Error: event.Message, Done: true}
			}
		}

		var sb strings.Builder

		if thinking.Len() > 0 {
			sb.WriteString("💭 **사고 과정**\n")
			thinkText := thinking.String()
			if len(thinkText) > 500 {
				thinkText = thinkText[:500] + "..."
			}
			sb.WriteString(thinkText)
			sb.WriteString("\n\n")
		}

		if reasoning.Len() > 0 {
			sb.WriteString("🧠 **추론 과정**\n")
			reasonText := reasoning.String()
			if len(reasonText) > 500 {
				reasonText = reasonText[:500] + "..."
			}
			sb.WriteString(reasonText)
			sb.WriteString("\n\n")
		}

		if len(tools) > 0 {
			sb.WriteString("🔧 **사용된 도구**: ")
			sb.WriteString(strings.Join(unique(tools), ", "))
			sb.WriteString("\n\n")
		}

		if result.Len() > 0 {
			sb.WriteString(result.String())
		} else {
			sb.WriteString("(응답 없음)")
		}

		return streamEvent{EventType: "done", Content: sb.String(), Done: true, SessionID: capturedSessionID}
	}
}

func streamClaudeCLI(prompt string, sessionID string) tea.Cmd {
	return func() tea.Msg {
		cwd, _ := os.Getwd()

		args := []string{
			"-p", prompt,
			"--print",
			"--permission-mode", "acceptEdits",
		}

		if sessionID != "" {
			args = append(args, "--resume", sessionID)
		}

		cmd := exec.Command("claude", args...)
		cmd.Dir = cwd

		output, err := cmd.CombinedOutput()
		if err != nil {
			return streamEvent{EventType: "error", Error: err.Error(), Done: true}
		}

		return streamEvent{EventType: "done", Content: string(output), Done: true}
	}
}

func unique(slice []string) []string {
	seen := make(map[string]bool)
	var result []string
	for _, s := range slice {
		if !seen[s] {
			seen[s] = true
			result = append(result, s)
		}
	}
	return result
}

func (m tuiModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd

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
			if m.cmd != nil && m.cmd.Process != nil {
				m.cmd.Process.Kill()
			}
			return m, tea.Quit

		case tea.KeyEnter:
			input := strings.TrimSpace(m.input.Value())
			if input != "" && !m.streaming {
				m.showWelcome = false
				m.streaming = true
				m.status = "처리 중..."
				m.currentOutput.Reset()

				m.messages = append(m.messages, chatMessage{
					msgType: msgUser,
					content: input,
					time:    time.Now(),
				})

				m.input.Reset()
				m.viewport.SetContent(m.renderContent())
				m.viewport.GotoBottom()

				if m.useSDK && m.bridge != nil {
					return m, streamWithSDK(m.bridge, input, m.sessionID)
				}
				return m, streamClaudeCLI(input, m.sessionID)
			}
		}

	case streamEvent:
		if msg.Done {
			m.streaming = false
			m.status = "ready"

			if msg.SessionID != "" {
				m.sessionID = msg.SessionID
			}

			content := msg.Content
			if msg.Error != "" {
				content = "❌ 오류: " + msg.Error
			}

			m.messages = append(m.messages, chatMessage{
				msgType: msgAssistant,
				content: content,
				time:    time.Now(),
			})

			m.viewport.SetContent(m.renderContent())
			m.viewport.GotoBottom()
		}

	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		cmds = append(cmds, cmd)
	}

	var tiCmd, vpCmd tea.Cmd
	m.input, tiCmd = m.input.Update(msg)
	m.viewport, vpCmd = m.viewport.Update(msg)
	cmds = append(cmds, tiCmd, vpCmd)

	return m, tea.Batch(cmds...)
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
	subtitle := subtitleStyle.Render("Multi-Agent Orchestrator")

	helpStyle := lipgloss.NewStyle().Foreground(textMuted).MarginTop(2)
	help := helpStyle.Render("메시지를 입력하고 Enter • Ctrl+C 종료")

	content := lipgloss.JoinVertical(lipgloss.Center, logo, subtitle, help)
	return lipgloss.Place(m.width, m.viewport.Height, lipgloss.Center, lipgloss.Center, content)
}

func (m tuiModel) renderMessages() string {
	var sb strings.Builder

	for i, msg := range m.messages {
		var borderCol lipgloss.Color
		var roleLabel string

		switch msg.msgType {
		case msgUser:
			borderCol = userBorder
			roleLabel = "나"
		case msgAssistant:
			borderCol = assistantBorder
			roleLabel = "AI"
		case msgThinking:
			borderCol = thinkingColor
			roleLabel = "💭 사고"
		case msgTool:
			borderCol = toolColor
			roleLabel = "🔧 " + msg.toolName
		}

		panelStyle := lipgloss.NewStyle().
			Background(bgPanel).
			Padding(1, 2).
			BorderLeft(true).
			BorderStyle(lipgloss.ThickBorder()).
			BorderForeground(borderCol).
			Width(m.width - 4)

		roleStyle := lipgloss.NewStyle().Foreground(textMuted)
		contentStyle := lipgloss.NewStyle().Foreground(textColor)

		panel := panelStyle.Render(roleStyle.Render(roleLabel) + "\n" + contentStyle.Render(msg.content))

		if i > 0 {
			sb.WriteString("\n")
		}
		sb.WriteString(panel)
	}

	if m.streaming {
		spinnerStyle := lipgloss.NewStyle().
			Background(bgPanel).
			Padding(1, 2).
			BorderLeft(true).
			BorderStyle(lipgloss.ThickBorder()).
			BorderForeground(accentColor).
			Width(m.width - 4)

		sb.WriteString("\n")
		sb.WriteString(spinnerStyle.Render(m.spinner.View() + " " + m.status))
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
	status := statusStyle.Render(fmt.Sprintf("claude • %d개 메시지", len(m.messages)))

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
		tea.WithInputTTY(),
	)

	_, err := p.Run()
	return err
}
