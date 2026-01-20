package lsp

type ServerConfig struct {
	Name         string
	Command      []string
	FilePatterns []string
	LanguageID   string
	InitOptions  map[string]any
	Settings     map[string]any
	Enabled      bool
	AutoStart    bool
}

var BuiltinServers = map[string]ServerConfig{
	"python": {
		Name:         "python",
		Command:      []string{"pylsp"},
		FilePatterns: []string{"*.py"},
		LanguageID:   "python",
		Settings: map[string]any{
			"pylsp": map[string]any{
				"plugins": map[string]any{
					"pycodestyle":     map[string]any{"enabled": true},
					"pyflakes":        map[string]any{"enabled": true},
					"pylint":          map[string]any{"enabled": false},
					"rope_completion": map[string]any{"enabled": true},
					"rope_rename":     map[string]any{"enabled": true},
				},
			},
		},
		Enabled: true,
	},
	"python-pyright": {
		Name:         "python-pyright",
		Command:      []string{"pyright-langserver", "--stdio"},
		FilePatterns: []string{"*.py"},
		LanguageID:   "python",
		Settings: map[string]any{
			"python": map[string]any{
				"analysis": map[string]any{
					"autoSearchPaths":       true,
					"diagnosticMode":        "workspace",
					"useLibraryCodeForTypes": true,
				},
			},
		},
		Enabled: true,
	},
	"typescript": {
		Name:         "typescript",
		Command:      []string{"typescript-language-server", "--stdio"},
		FilePatterns: []string{"*.ts", "*.tsx", "*.js", "*.jsx"},
		LanguageID:   "typescript",
		InitOptions: map[string]any{
			"preferences": map[string]any{
				"includeInlayParameterNameHints": "all",
				"includeInlayVariableTypeHints":  true,
			},
		},
		Enabled: true,
	},
	"rust": {
		Name:         "rust",
		Command:      []string{"rust-analyzer"},
		FilePatterns: []string{"*.rs"},
		LanguageID:   "rust",
		Settings: map[string]any{
			"rust-analyzer": map[string]any{
				"checkOnSave": map[string]any{"command": "clippy"},
			},
		},
		Enabled: true,
	},
	"go": {
		Name:         "go",
		Command:      []string{"gopls"},
		FilePatterns: []string{"*.go"},
		LanguageID:   "go",
		Settings: map[string]any{
			"gopls": map[string]any{
				"staticcheck":     true,
				"usePlaceholders": true,
			},
		},
		Enabled: true,
	},
	"c-cpp": {
		Name:         "c-cpp",
		Command:      []string{"clangd"},
		FilePatterns: []string{"*.c", "*.cpp", "*.h", "*.hpp", "*.cc"},
		LanguageID:   "cpp",
		Enabled:      true,
	},
	"json": {
		Name:         "json",
		Command:      []string{"vscode-json-language-server", "--stdio"},
		FilePatterns: []string{"*.json", "*.jsonc"},
		LanguageID:   "json",
		Enabled:      true,
	},
	"yaml": {
		Name:         "yaml",
		Command:      []string{"yaml-language-server", "--stdio"},
		FilePatterns: []string{"*.yaml", "*.yml"},
		LanguageID:   "yaml",
		Enabled:      true,
	},
}

func GetServerConfig(name string) *ServerConfig {
	if cfg, ok := BuiltinServers[name]; ok {
		return &cfg
	}
	return nil
}

func GetServerForFile(filePath string) *ServerConfig {
	for _, cfg := range BuiltinServers {
		if !cfg.Enabled {
			continue
		}
		for _, pattern := range cfg.FilePatterns {
			if matchPattern(filePath, pattern) {
				return &cfg
			}
		}
	}
	return nil
}

func matchPattern(path, pattern string) bool {
	if len(pattern) == 0 {
		return false
	}
	if pattern[0] == '*' {
		suffix := pattern[1:]
		return len(path) >= len(suffix) && path[len(path)-len(suffix):] == suffix
	}
	return path == pattern
}

func ListBuiltinServers() []string {
	names := make([]string, 0, len(BuiltinServers))
	for name := range BuiltinServers {
		names = append(names, name)
	}
	return names
}
