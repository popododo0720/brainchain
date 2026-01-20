package context

const CharsPerToken = 4

var ModelLimits = map[string]int{
	"claude-opus":   200000,
	"claude-sonnet": 200000,
	"claude-haiku":  200000,
	"opus":          200000,
	"sonnet":        200000,
	"haiku":         200000,
	"gpt-5.2":       128000,
	"gpt-4":         128000,
	"gpt-4o":        128000,
	"codex":         128000,
	"default":       100000,
}

type TokenCounter struct {
	Model string
}

func NewTokenCounter(model string) *TokenCounter {
	if model == "" {
		model = "default"
	}
	return &TokenCounter{Model: model}
}

func (c *TokenCounter) Count(text string) int {
	if text == "" {
		return 0
	}
	return len(text) / CharsPerToken
}

func (c *TokenCounter) CountMessages(messages []Message) int {
	total := 0
	for _, msg := range messages {
		total += c.Count(msg.Content)
		total += 10
	}
	return total
}

func (c *TokenCounter) GetLimit() int {
	if limit, ok := ModelLimits[c.Model]; ok {
		return limit
	}
	return ModelLimits["default"]
}

func (c *TokenCounter) UsagePercent(messages []Message) float64 {
	used := c.CountMessages(messages)
	limit := c.GetLimit()
	if limit <= 0 {
		return 0
	}
	return float64(used) / float64(limit)
}

func (c *TokenCounter) RemainingTokens(messages []Message) int {
	used := c.CountMessages(messages)
	limit := c.GetLimit()
	return limit - used
}

func (c *TokenCounter) FormatUsage(messages []Message) string {
	used := c.CountMessages(messages)
	limit := c.GetLimit()
	percent := 0.0
	if limit > 0 {
		percent = float64(used) / float64(limit) * 100
	}
	return formatNumber(used) + " / " + formatNumber(limit) + " (" + formatPercent(percent) + ")"
}

func formatNumber(n int) string {
	if n < 1000 {
		return itoa(n)
	}
	return itoa(n/1000) + "," + padZero(n%1000, 3)
}

func formatPercent(p float64) string {
	return itoa(int(p)) + "%"
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	s := ""
	for n > 0 {
		s = string(rune('0'+n%10)) + s
		n /= 10
	}
	return s
}

func padZero(n, width int) string {
	s := itoa(n)
	for len(s) < width {
		s = "0" + s
	}
	return s
}

type Message struct {
	Role    string
	Content string
}
