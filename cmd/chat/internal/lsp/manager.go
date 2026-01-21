package lsp

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// Manager handles LSP server lifecycle and client management
type Manager struct {
	workspaceRoot string
	clients       map[string]*Client
	mu            sync.RWMutex
	timeout       time.Duration
	lspDir        string
}

// NewManager creates a new LSP manager
func NewManager(workspaceRoot string, lspDir string) *Manager {
	if lspDir == "" {
		lspDir = filepath.Join(homeDir(), ".config", "brainchain", "lsp-servers")
	}
	return &Manager{
		workspaceRoot: workspaceRoot,
		clients:       make(map[string]*Client),
		timeout:       30 * time.Second,
		lspDir:        lspDir,
	}
}

// GetClientForFile returns an LSP client for the given file, starting the server if needed
func (m *Manager) GetClientForFile(filePath string) (*Client, error) {
	serverName := m.detectLanguage(filePath)
	if serverName == "" {
		return nil, fmt.Errorf("no LSP server configured for file: %s", filePath)
	}

	return m.GetClient(serverName)
}

// GetClient returns an LSP client by server name, starting if needed
func (m *Manager) GetClient(serverName string) (*Client, error) {
	m.mu.RLock()
	if client, ok := m.clients[serverName]; ok && client.IsConnected() {
		m.mu.RUnlock()
		return client, nil
	}
	m.mu.RUnlock()

	return m.startServer(serverName)
}

// detectLanguage returns the server name for a given file path
func (m *Manager) detectLanguage(filePath string) string {
	ext := strings.ToLower(filepath.Ext(filePath))

	extMap := map[string]string{
		".go":   "go",
		".py":   "python-pyright",
		".rs":   "rust",
		".ts":   "typescript",
		".tsx":  "typescript",
		".js":   "typescript",
		".jsx":  "typescript",
		".c":    "c-cpp",
		".cpp":  "c-cpp",
		".cc":   "c-cpp",
		".h":    "c-cpp",
		".hpp":  "c-cpp",
		".json": "json",
		".yaml": "yaml",
		".yml":  "yaml",
	}

	if server, ok := extMap[ext]; ok {
		return server
	}
	return ""
}

// startServer starts an LSP server and returns the client
func (m *Manager) startServer(serverName string) (*Client, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if client, ok := m.clients[serverName]; ok && client.IsConnected() {
		return client, nil
	}

	config := GetServerConfig(serverName)
	if config == nil {
		return nil, fmt.Errorf("unknown LSP server: %s", serverName)
	}

	if !config.Enabled {
		return nil, fmt.Errorf("LSP server %s is disabled", serverName)
	}

	resolvedCmd, err := m.resolveCommand(config)
	if err != nil {
		return nil, fmt.Errorf("LSP server %s not available: %w", serverName, err)
	}

	resolvedConfig := *config
	resolvedConfig.Command = resolvedCmd

	client := NewClient(&resolvedConfig, m.workspaceRoot, m.timeout)
	if err := client.Connect(); err != nil {
		return nil, fmt.Errorf("failed to start LSP server %s: %w", serverName, err)
	}

	m.clients[serverName] = client
	return client, nil
}

// resolveCommand finds the actual command to run, checking bundled and system paths
func (m *Manager) resolveCommand(config *ServerConfig) ([]string, error) {
	if len(config.Command) == 0 {
		return nil, fmt.Errorf("no command specified")
	}

	cmd := config.Command[0]
	args := config.Command[1:]

	bundledPath := filepath.Join(m.lspDir, cmd)
	if isExecutable(bundledPath) {
		return append([]string{bundledPath}, args...), nil
	}

	if path, err := exec.LookPath(cmd); err == nil {
		return append([]string{path}, args...), nil
	}

	npmBinPath := filepath.Join(m.lspDir, "node_modules", ".bin", cmd)
	if isExecutable(npmBinPath) {
		return append([]string{npmBinPath}, args...), nil
	}

	commonPaths := []string{
		filepath.Join(homeDir(), ".local", "bin", cmd),
		filepath.Join(homeDir(), "go", "bin", cmd),
		filepath.Join(homeDir(), ".cargo", "bin", cmd),
		filepath.Join("/usr", "local", "bin", cmd),
		filepath.Join(homeDir(), ".npm-global", "bin", cmd),
	}

	for _, p := range commonPaths {
		if isExecutable(p) {
			return append([]string{p}, args...), nil
		}
	}

	return nil, fmt.Errorf("command not found: %s", cmd)
}

// StopServer stops a specific LSP server
func (m *Manager) StopServer(serverName string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if client, ok := m.clients[serverName]; ok {
		client.Disconnect()
		delete(m.clients, serverName)
	}
}

// StopAll stops all running LSP servers
func (m *Manager) StopAll() {
	m.mu.Lock()
	defer m.mu.Unlock()

	for name, client := range m.clients {
		client.Disconnect()
		delete(m.clients, name)
	}
}

// ListActive returns names of all active LSP servers
func (m *Manager) ListActive() []string {
	m.mu.RLock()
	defer m.mu.RUnlock()

	var active []string
	for name, client := range m.clients {
		if client.IsConnected() {
			active = append(active, name)
		}
	}
	return active
}

// IsServerAvailable checks if an LSP server is available (installed)
func (m *Manager) IsServerAvailable(serverName string) bool {
	config := GetServerConfig(serverName)
	if config == nil || !config.Enabled {
		return false
	}

	_, err := m.resolveCommand(config)
	return err == nil
}

// ListAvailable returns all available (installed) LSP servers
func (m *Manager) ListAvailable() []string {
	var available []string
	for name := range BuiltinServers {
		if m.IsServerAvailable(name) {
			available = append(available, name)
		}
	}
	return available
}

// ListConfigured returns all configured (but not necessarily installed) LSP servers
func (m *Manager) ListConfigured() []string {
	return ListBuiltinServers()
}

// Definition finds the definition of a symbol at the given position
func (m *Manager) Definition(filePath string, line, character int) ([]Location, error) {
	client, err := m.GetClientForFile(filePath)
	if err != nil {
		return nil, err
	}
	return client.Definition(filePath, line, character)
}

// References finds all references to a symbol at the given position
func (m *Manager) References(filePath string, line, character int, includeDeclaration bool) ([]Location, error) {
	client, err := m.GetClientForFile(filePath)
	if err != nil {
		return nil, err
	}
	return client.References(filePath, line, character, includeDeclaration)
}

// Hover returns hover information at the given position
func (m *Manager) Hover(filePath string, line, character int) (*HoverResult, error) {
	client, err := m.GetClientForFile(filePath)
	if err != nil {
		return nil, err
	}
	return client.Hover(filePath, line, character)
}

// Rename renames a symbol at the given position
func (m *Manager) Rename(filePath string, line, character int, newName string) (*WorkspaceEdit, error) {
	client, err := m.GetClientForFile(filePath)
	if err != nil {
		return nil, err
	}
	return client.Rename(filePath, line, character, newName)
}

// PrepareRename checks if rename is valid at the given position
func (m *Manager) PrepareRename(filePath string, line, character int) (*Range, error) {
	client, err := m.GetClientForFile(filePath)
	if err != nil {
		return nil, err
	}
	return client.PrepareRename(filePath, line, character)
}

// Diagnostics returns diagnostics for a file
func (m *Manager) Diagnostics(filePath string) ([]Diagnostic, error) {
	client, err := m.GetClientForFile(filePath)
	if err != nil {
		return nil, err
	}
	return client.Diagnostics(filePath)
}

// DocumentSymbols returns symbols in a document
func (m *Manager) DocumentSymbols(filePath string) ([]Symbol, error) {
	client, err := m.GetClientForFile(filePath)
	if err != nil {
		return nil, err
	}
	return client.DocumentSymbols(filePath)
}

// WorkspaceSymbols searches for symbols across the workspace
func (m *Manager) WorkspaceSymbols(serverName, query string) ([]Symbol, error) {
	client, err := m.GetClient(serverName)
	if err != nil {
		return nil, err
	}
	return client.WorkspaceSymbols(query)
}

func homeDir() string {
	if home, err := os.UserHomeDir(); err == nil {
		return home
	}
	return "/root"
}

func isExecutable(path string) bool {
	cmd := exec.Command("test", "-x", path)
	return cmd.Run() == nil
}
