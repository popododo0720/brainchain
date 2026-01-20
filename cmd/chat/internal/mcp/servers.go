package mcp

type ServerConfig struct {
	Name        string
	Command     []string
	Args        map[string]any
	Env         map[string]string
	Enabled     bool
	AutoConnect bool
	Timeout     int
}

func (c ServerConfig) WithArgs(args map[string]any) ServerConfig {
	newArgs := make(map[string]any)
	for k, v := range c.Args {
		newArgs[k] = v
	}
	for k, v := range args {
		newArgs[k] = v
	}
	c.Args = newArgs
	return c
}

var BuiltinServers = map[string]ServerConfig{
	"filesystem": {
		Name:    "filesystem",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-filesystem"},
		Args:    map[string]any{"allowed_paths": []string{"."}},
		Enabled: true,
	},
	"fetch": {
		Name:    "fetch",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-fetch"},
		Enabled: false,
	},
	"memory": {
		Name:    "memory",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-memory"},
		Enabled: false,
	},
	"puppeteer": {
		Name:    "puppeteer",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-puppeteer"},
		Enabled: false,
	},
	"brave-search": {
		Name:    "brave-search",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-brave-search"},
		Env:     map[string]string{"BRAVE_API_KEY": ""},
		Enabled: false,
	},
	"github": {
		Name:    "github",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-github"},
		Env:     map[string]string{"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
		Enabled: false,
	},
	"postgres": {
		Name:    "postgres",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-postgres"},
		Args:    map[string]any{"connection_string": ""},
		Enabled: false,
	},
	"sqlite": {
		Name:    "sqlite",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-sqlite"},
		Args:    map[string]any{"database_path": ""},
		Enabled: false,
	},
	"slack": {
		Name:    "slack",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-slack"},
		Env:     map[string]string{"SLACK_BOT_TOKEN": "", "SLACK_TEAM_ID": ""},
		Enabled: false,
	},
	"google-maps": {
		Name:    "google-maps",
		Command: []string{"npx", "-y", "@modelcontextprotocol/server-google-maps"},
		Env:     map[string]string{"GOOGLE_MAPS_API_KEY": ""},
		Enabled: false,
	},
}

func GetServerConfig(name string) *ServerConfig {
	if cfg, ok := BuiltinServers[name]; ok {
		return &cfg
	}
	return nil
}

func ListBuiltinServers() []string {
	names := make([]string, 0, len(BuiltinServers))
	for name := range BuiltinServers {
		names = append(names, name)
	}
	return names
}

func CreateServerConfig(command []string, name string, opts ...func(*ServerConfig)) ServerConfig {
	cfg := ServerConfig{
		Command: command,
		Name:    name,
		Timeout: 30,
		Enabled: true,
	}
	for _, opt := range opts {
		opt(&cfg)
	}
	return cfg
}
