package adapter

import "os/exec"

var registry = map[string]func() Adapter{
	"claude":        func() Adapter { return NewClaudeAdapter(nil) },
	"claude-sonnet": func() Adapter { return NewClaudeSonnetAdapter() },
	"claude-opus":   func() Adapter { return NewClaudeOpusAdapter() },
	"claude-haiku":  func() Adapter { return NewClaudeHaikuAdapter() },
	"codex":         func() Adapter { return NewCodexAdapter(nil) },
}

func Get(name string) Adapter {
	if factory, ok := registry[name]; ok {
		return factory()
	}
	return nil
}

func GetAvailable() Adapter {
	priority := []string{"claude", "codex"}
	for _, name := range priority {
		if _, err := exec.LookPath(name); err == nil {
			return Get(name)
		}
	}
	return nil
}

func ListAvailable() []string {
	var available []string
	for name := range registry {
		if adapter := Get(name); adapter != nil && adapter.IsAvailable() {
			available = append(available, name)
		}
	}
	return available
}

func Register(name string, factory func() Adapter) {
	registry[name] = factory
}
