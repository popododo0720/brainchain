package context

import (
	"os/exec"
	"strings"
	"time"

	"github.com/google/uuid"
)

type CompressionConfig struct {
	KeepRecent             int
	MaxMessages            int
	UseAISummary           bool
	SummaryAgent           string
	PruneToolOutputsAfter  int
}

func DefaultCompressionConfig() CompressionConfig {
	return CompressionConfig{
		KeepRecent:            10,
		MaxMessages:           50,
		UseAISummary:          true,
		SummaryAgent:          "claude-haiku",
		PruneToolOutputsAfter: 20,
	}
}

type CompressionResult struct {
	OriginalCount   int
	CompressedCount int
	TokensSaved     int
	Summary         string
	PrunedMessages  []string
}

type SessionMessage struct {
	ID        string
	SessionID string
	Timestamp time.Time
	Role      string
	Content   string
	StepIndex *int
	TaskID    *string
}

type Compressor struct {
	Config CompressionConfig
}

func NewCompressor(config *CompressionConfig) *Compressor {
	if config == nil {
		cfg := DefaultCompressionConfig()
		config = &cfg
	}
	return &Compressor{Config: *config}
}

func (c *Compressor) SummarizeMessages(messages []SessionMessage, keepRecent int) ([]SessionMessage, *SessionMessage) {
	if keepRecent <= 0 {
		keepRecent = c.Config.KeepRecent
	}

	if len(messages) <= keepRecent {
		return messages, nil
	}

	toSummarize := messages[:len(messages)-keepRecent]
	toKeep := messages[len(messages)-keepRecent:]

	var summaryText string
	if c.Config.UseAISummary {
		summaryText = c.generateAISummary(toSummarize)
	} else {
		summaryText = c.generateSimpleSummary(toSummarize)
	}

	sessionID := ""
	if len(messages) > 0 {
		sessionID = messages[0].SessionID
	}

	summaryMessage := &SessionMessage{
		ID:        "summary-" + uuid.New().String()[:8],
		SessionID: sessionID,
		Timestamp: time.Now(),
		Role:      "system",
		Content:   "[Session Summary]\n" + summaryText,
	}

	return toKeep, summaryMessage
}

func (c *Compressor) PruneToolOutputs(messages []SessionMessage) []SessionMessage {
	threshold := c.Config.PruneToolOutputsAfter

	if len(messages) <= threshold {
		return messages
	}

	result := make([]SessionMessage, len(messages))
	for i, msg := range messages {
		if i < len(messages)-threshold && c.isToolOutput(msg) {
			result[i] = c.pruneMessage(msg)
		} else {
			result[i] = msg
		}
	}

	return result
}

func (c *Compressor) CompactSession(sessionID string, messages []SessionMessage, initialPrompt string) (*SessionMessage, error) {
	summaryText := c.generateComprehensiveSummary(sessionID, messages, initialPrompt)

	summaryMessage := &SessionMessage{
		ID:        "compact-" + uuid.New().String()[:8],
		SessionID: sessionID,
		Timestamp: time.Now(),
		Role:      "system",
		Content:   "[Compacted Session - Previous: " + sessionID + "]\n\n" + summaryText,
	}

	return summaryMessage, nil
}

func (c *Compressor) generateAISummary(messages []SessionMessage) string {
	var sb strings.Builder
	for _, msg := range messages {
		content := msg.Content
		if len(content) > 500 {
			content = content[:500] + "..."
		}
		sb.WriteString("[" + msg.Role + "]: " + content + "\n")
	}

	prompt := `Summarize the following conversation history in 2-3 concise paragraphs.
Focus on:
1. Key decisions and outcomes
2. Important code changes or findings
3. Current state and next steps

Conversation:
` + sb.String() + `

Summary:`

	cmd := exec.Command("claude", "-p", prompt, "--print")
	output, err := cmd.Output()
	if err == nil && len(output) > 0 {
		return strings.TrimSpace(string(output))
	}

	return c.generateSimpleSummary(messages)
}

func (c *Compressor) generateSimpleSummary(messages []SessionMessage) string {
	var sb strings.Builder
	sb.WriteString("Summarized " + itoa(len(messages)) + " messages.\n")

	roles := make(map[string]int)
	for _, msg := range messages {
		roles[msg.Role]++
	}

	sb.WriteString("Roles: ")
	first := true
	for role, count := range roles {
		if !first {
			sb.WriteString(", ")
		}
		sb.WriteString(role + "(" + itoa(count) + ")")
		first = false
	}
	sb.WriteString("\n")

	if len(messages) > 0 {
		firstContent := messages[0].Content
		if len(firstContent) > 100 {
			firstContent = firstContent[:100]
		}
		sb.WriteString("Started with: " + firstContent + "...\n")

		lastContent := messages[len(messages)-1].Content
		if len(lastContent) > 100 {
			lastContent = lastContent[:100]
		}
		sb.WriteString("Ended with: " + lastContent + "...\n")
	}

	return sb.String()
}

func (c *Compressor) generateComprehensiveSummary(sessionID string, messages []SessionMessage, initialPrompt string) string {
	var sb strings.Builder
	sb.WriteString("Session: " + sessionID + "\n")
	sb.WriteString("Initial prompt: " + initialPrompt + "\n")
	sb.WriteString("Messages: " + itoa(len(messages)) + "\n\n")
	sb.WriteString("Recent conversation:\n")

	start := 0
	if len(messages) > 10 {
		start = len(messages) - 10
	}
	for _, msg := range messages[start:] {
		content := msg.Content
		if len(content) > 300 {
			content = content[:300] + "..."
		}
		sb.WriteString("\n[" + msg.Role + "]: " + content)
	}

	prompt := `Create a comprehensive summary of this session for context continuation.

` + sb.String() + `

Include:
1. Original goal/task
2. Key decisions and implementations
3. Current state
4. Any pending items

Summary:`

	cmd := exec.Command("claude", "-p", prompt, "--print")
	output, err := cmd.Output()
	if err == nil && len(output) > 0 {
		return strings.TrimSpace(string(output))
	}

	return c.generateSimpleSummary(messages)
}

func (c *Compressor) isToolOutput(msg SessionMessage) bool {
	indicators := []string{"```", "File:", "Output:", "Result:", "[tool]", "function_call"}
	for _, ind := range indicators {
		if strings.Contains(msg.Content, ind) {
			return true
		}
	}
	return false
}

func (c *Compressor) pruneMessage(msg SessionMessage) SessionMessage {
	content := msg.Content
	if len(content) > 200 {
		content = content[:200] + "\n[... " + itoa(len(msg.Content)-200) + " chars pruned ...]"
	}

	return SessionMessage{
		ID:        msg.ID,
		SessionID: msg.SessionID,
		Timestamp: msg.Timestamp,
		Role:      msg.Role,
		Content:   content,
		StepIndex: msg.StepIndex,
		TaskID:    msg.TaskID,
	}
}
