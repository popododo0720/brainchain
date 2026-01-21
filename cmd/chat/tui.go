package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"brainchain/cmd/chat/internal/config"
	"brainchain/cmd/chat/internal/sdk"
	"brainchain/cmd/chat/internal/session"

	"github.com/charmbracelet/bubbles/list"
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
	
	streamThinking  strings.Builder
	streamReasoning strings.Builder
	streamText      strings.Builder
	streamTools     []string
	streamCancel    chan struct{}

	showPalette     bool
	paletteList     list.Model
	sessionMgr      *session.Manager
	sessions        []*session.Session
	showSessionList bool
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

	if mgr, err := session.NewManager("", true); err == nil {
		m.sessionMgr = mgr
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
	Delta     string
}

type sdkEventMsg struct {
	event   sdk.Event
	eventCh chan sdk.Event
}

func (m tuiModel) Init() tea.Cmd {
	return tea.Batch(textinput.Blink, m.spinner.Tick)
}

func startSDKStream(bridge *sdk.Bridge, prompt string, sessionID string) tea.Cmd {
	return func() tea.Msg {
		eventCh := make(chan sdk.Event, 100)
		
		go func() {
			bridge.Chat(prompt, sessionID, eventCh)
			close(eventCh)
		}()

		return sdkEventMsg{eventCh: eventCh}
	}
}

func waitForSDKEvent(eventCh chan sdk.Event) tea.Cmd {
	return func() tea.Msg {
		event, ok := <-eventCh
		if !ok {
			return streamEvent{EventType: "done", Done: true}
		}
		return sdkEventMsg{event: event, eventCh: eventCh}
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
		if m.showPalette || m.showSessionList {
			return m.handlePaletteKeys(msg)
		}

		switch msg.Type {
		case tea.KeyCtrlQ:
			if m.sessionMgr != nil {
				m.sessionMgr.Close()
			}
			return m, tea.Quit

		case tea.KeyEsc:
			if m.streaming {
				if m.streamCancel != nil {
					close(m.streamCancel)
					m.streamCancel = nil
				}
				m.streaming = false
				m.status = "중단됨"
				m.messages = append(m.messages, chatMessage{
					msgType: msgAssistant,
					content: "⚠️ 대화가 중단되었습니다.",
					time:    time.Now(),
				})
				m.viewport.SetContent(m.renderContent())
				m.viewport.GotoBottom()
			}
			return m, nil

		case tea.KeyCtrlP:
			m.showPalette = true
			m.paletteList = m.createPaletteList()
			return m, nil

		case tea.KeyEnter:
			input := strings.TrimSpace(m.input.Value())
			if input != "" && !m.streaming {
				m.showWelcome = false
				m.streaming = true
				m.status = "처리 중..."
				m.currentOutput.Reset()
				m.streamCancel = make(chan struct{})

				m.messages = append(m.messages, chatMessage{
					msgType: msgUser,
					content: input,
					time:    time.Now(),
				})

				m.saveMessage("user", input)

				m.input.Reset()
				m.viewport.SetContent(m.renderContent())
				m.viewport.GotoBottom()

				m.streamThinking.Reset()
				m.streamReasoning.Reset()
				m.streamText.Reset()
				m.streamTools = nil

				if m.useSDK && m.bridge != nil {
					return m, startSDKStream(m.bridge, input, m.sessionID)
				}
				return m, streamClaudeCLI(input, m.sessionID)
			}
		}

	case sdkEventMsg:
		if msg.eventCh == nil {
			break
		}
		
		event := msg.event
		switch event.Type {
		case sdk.EventSystem:
			if event.SessionID != "" {
				m.sessionID = event.SessionID
			}
		case sdk.EventThinking:
			m.streamThinking.Reset()
			m.streamThinking.WriteString(event.Content)
			m.status = "💭 사고 중..."
		case sdk.EventReasoning:
			m.streamReasoning.Reset()
			m.streamReasoning.WriteString(event.Content)
			m.status = "🧠 추론 중..."
		case sdk.EventText:
			m.streamText.Reset()
			m.streamText.WriteString(event.Content)
			m.status = "✍️ 작성 중..."
		case sdk.EventToolStart:
			m.streamTools = append(m.streamTools, event.Name)
			m.status = "🔧 " + event.Name
		case sdk.EventError:
			m.streaming = false
			m.status = "ready"
			m.messages = append(m.messages, chatMessage{
				msgType: msgAssistant,
				content: "❌ 오류: " + event.Message,
				time:    time.Now(),
			})
			m.viewport.SetContent(m.renderContent())
			m.viewport.GotoBottom()
			return m, nil
		}

		m.viewport.SetContent(m.renderContent())
		m.viewport.GotoBottom()
		return m, waitForSDKEvent(msg.eventCh)

	case streamEvent:
		if msg.Done {
			m.streaming = false
			m.status = "ready"

			if msg.SessionID != "" {
				m.sessionID = msg.SessionID
			}

			var content string
			if msg.Content != "" {
				content = msg.Content
			} else {
				var sb strings.Builder
				if m.streamThinking.Len() > 0 {
					sb.WriteString("💭 **사고 과정**\n")
					thinkText := m.streamThinking.String()
					if len(thinkText) > 500 {
						thinkText = thinkText[:500] + "..."
					}
					sb.WriteString(thinkText)
					sb.WriteString("\n\n")
				}
				if m.streamReasoning.Len() > 0 {
					sb.WriteString("🧠 **추론 과정**\n")
					reasonText := m.streamReasoning.String()
					if len(reasonText) > 500 {
						reasonText = reasonText[:500] + "..."
					}
					sb.WriteString(reasonText)
					sb.WriteString("\n\n")
				}
				if len(m.streamTools) > 0 {
					sb.WriteString("🔧 **사용된 도구**: ")
					sb.WriteString(strings.Join(unique(m.streamTools), ", "))
					sb.WriteString("\n\n")
				}
				if m.streamText.Len() > 0 {
					sb.WriteString(m.streamText.String())
				} else {
					sb.WriteString("(응답 없음)")
				}
				content = sb.String()
			}

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
		panelStyle := lipgloss.NewStyle().
			Background(bgPanel).
			Padding(1, 2).
			BorderLeft(true).
			BorderStyle(lipgloss.ThickBorder()).
			BorderForeground(accentColor).
			Width(m.width - 4)

		roleStyle := lipgloss.NewStyle().Foreground(textMuted)
		contentStyle := lipgloss.NewStyle().Foreground(textColor)
		thinkStyle := lipgloss.NewStyle().Foreground(thinkingColor)

		var streamContent strings.Builder
		streamContent.WriteString(m.spinner.View() + " " + m.status + "\n\n")

		if m.streamThinking.Len() > 0 {
			thinkText := m.streamThinking.String()
			if len(thinkText) > 300 {
				thinkText = thinkText[len(thinkText)-300:]
			}
			streamContent.WriteString(thinkStyle.Render("💭 " + thinkText))
			streamContent.WriteString("\n")
		}

		if m.streamText.Len() > 0 {
			streamContent.WriteString(contentStyle.Render(m.streamText.String()))
		}

		sb.WriteString("\n")
		sb.WriteString(panelStyle.Render(roleStyle.Render("AI") + "\n" + streamContent.String()))
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

	base := lipgloss.JoinVertical(lipgloss.Left, headerLine, m.viewport.View(), inputArea, footer)

	if m.showPalette || m.showSessionList {
		return m.renderWithOverlay(base)
	}

	return base
}

func runTUI() error {
	p := tea.NewProgram(
		newTUIModel(),
		tea.WithAltScreen(),
		tea.WithMouseCellMotion(),
	)

	_, err := p.Run()
	return err
}

type paletteItem struct {
	title string
	desc  string
	cmd   string
}

func (i paletteItem) Title() string       { return i.title }
func (i paletteItem) Description() string { return i.desc }
func (i paletteItem) FilterValue() string { return i.title }

func (m *tuiModel) createPaletteList() list.Model {
	items := []list.Item{
		paletteItem{"Switch Session", "이전 세션으로 전환", "switch_session"},
		paletteItem{"New Session", "새 세션 시작", "new_session"},
		paletteItem{"Clear Messages", "현재 대화 지우기", "clear"},
	}

	delegate := list.NewDefaultDelegate()
	delegate.Styles.SelectedTitle = delegate.Styles.SelectedTitle.Foreground(accentColor)
	delegate.Styles.SelectedDesc = delegate.Styles.SelectedDesc.Foreground(textMuted)

	l := list.New(items, delegate, 40, 10)
	l.Title = "Command Palette"
	l.SetShowStatusBar(false)
	l.SetFilteringEnabled(true)
	l.Styles.Title = lipgloss.NewStyle().Foreground(accentColor).Bold(true)

	return l
}

func (m *tuiModel) createSessionList() list.Model {
	var items []list.Item

	if m.sessionMgr != nil {
		sessions, _ := m.sessionMgr.ListSessions("", 20)
		m.sessions = sessions
		for _, s := range sessions {
			preview := s.InitialPrompt
			if len(preview) > 40 {
				preview = preview[:40] + "..."
			}
			items = append(items, paletteItem{
				title: s.DisplayName(),
				desc:  preview,
				cmd:   s.ID,
			})
		}
	}

	if len(items) == 0 {
		items = append(items, paletteItem{"No sessions", "세션이 없습니다", ""})
	}

	delegate := list.NewDefaultDelegate()
	l := list.New(items, delegate, 50, 15)
	l.Title = "Sessions"
	l.SetShowStatusBar(false)
	l.SetFilteringEnabled(true)
	l.Styles.Title = lipgloss.NewStyle().Foreground(accentColor).Bold(true)

	return l
}

func (m tuiModel) handlePaletteKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.Type {
	case tea.KeyEsc:
		m.showPalette = false
		m.showSessionList = false
		return m, nil

	case tea.KeyEnter:
		if m.showSessionList {
			if item, ok := m.paletteList.SelectedItem().(paletteItem); ok && item.cmd != "" {
				m.switchToSession(item.cmd)
			}
			m.showSessionList = false
			m.showPalette = false
			return m, nil
		}

		if item, ok := m.paletteList.SelectedItem().(paletteItem); ok {
			switch item.cmd {
			case "switch_session":
				m.showPalette = false
				m.showSessionList = true
				m.paletteList = m.createSessionList()
			case "new_session":
				m.startNewSession()
				m.showPalette = false
			case "clear":
				m.messages = nil
				m.showWelcome = true
				m.showPalette = false
				m.viewport.SetContent(m.renderContent())
			}
		}
		return m, nil
	}

	var cmd tea.Cmd
	m.paletteList, cmd = m.paletteList.Update(msg)
	return m, cmd
}

func (m tuiModel) renderWithOverlay(base string) string {
	overlay := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(accentColor).
		Background(lipgloss.Color("#1e1e2e")).
		Padding(1, 2).
		Width(m.width / 2).
		Render(m.paletteList.View())

	return lipgloss.Place(m.width, m.height, lipgloss.Center, lipgloss.Center, overlay,
		lipgloss.WithWhitespaceBackground(lipgloss.Color("#00000088")))
}

func (m *tuiModel) saveMessage(role, content string) {
	if m.sessionMgr == nil {
		return
	}
	m.sessionMgr.AddMessage(m.sessionID, role, content, nil, "")
}

func (m *tuiModel) startNewSession() {
	if m.sessionMgr == nil {
		return
	}
	m.messages = nil
	m.showWelcome = true
	m.sessionID = ""
	cwd, _ := os.Getwd()
	if sess, err := m.sessionMgr.CreateSession("", cwd, "chat", nil); err == nil && sess != nil {
		m.sessionID = sess.ID
	}
	m.viewport.SetContent(m.renderContent())
}

func (m *tuiModel) switchToSession(sessionID string) {
	if m.sessionMgr == nil {
		return
	}

	m.sessionID = sessionID
	m.messages = nil
	m.showWelcome = false

	msgs, _ := m.sessionMgr.GetMessages(sessionID)
	for _, msg := range msgs {
		msgType := msgAssistant
		if msg.Role == "user" {
			msgType = msgUser
		}
		m.messages = append(m.messages, chatMessage{
			msgType: msgType,
			content: msg.Content,
			time:    msg.Timestamp,
		})
	}

	m.viewport.SetContent(m.renderContent())
	m.viewport.GotoBottom()
}
