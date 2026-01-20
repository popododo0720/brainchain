package plugin

import (
	"os"
	"path/filepath"
	"plugin"
)

type PluginInfo struct {
	Name        string
	Version     string
	Description string
	Author      string
	Path        string
	Module      *plugin.Plugin
	Enabled     bool
	Commands    []string
	Hooks       []string
	Adapters    []string
}

type Loader struct {
	searchPaths []string
	loaded      map[string]*PluginInfo
}

func NewLoader() *Loader {
	l := &Loader{
		loaded: make(map[string]*PluginInfo),
	}

	home, err := os.UserHomeDir()
	if err == nil {
		configPlugins := filepath.Join(home, ".config", "brainchain", "plugins")
		if info, err := os.Stat(configPlugins); err == nil && info.IsDir() {
			l.searchPaths = append(l.searchPaths, configPlugins)
		}
	}

	cwd, err := os.Getwd()
	if err == nil {
		localPlugins := filepath.Join(cwd, "brainchain_plugins")
		if info, err := os.Stat(localPlugins); err == nil && info.IsDir() {
			l.searchPaths = append(l.searchPaths, localPlugins)
		}
	}

	return l
}

func (l *Loader) AddSearchPath(path string) {
	if info, err := os.Stat(path); err == nil && info.IsDir() {
		for _, p := range l.searchPaths {
			if p == path {
				return
			}
		}
		l.searchPaths = append(l.searchPaths, path)
	}
}

func (l *Loader) Discover() []*PluginInfo {
	var plugins []*PluginInfo

	for _, searchPath := range l.searchPaths {
		entries, err := os.ReadDir(searchPath)
		if err != nil {
			continue
		}

		for _, entry := range entries {
			if !entry.IsDir() && filepath.Ext(entry.Name()) == ".so" {
				info := l.loadPluginInfo(filepath.Join(searchPath, entry.Name()))
				if info != nil {
					plugins = append(plugins, info)
				}
			}
		}
	}

	return plugins
}

func (l *Loader) loadPluginInfo(path string) *PluginInfo {
	p, err := plugin.Open(path)
	if err != nil {
		return nil
	}

	info := &PluginInfo{
		Name:    filepath.Base(path),
		Path:    path,
		Module:  p,
		Enabled: true,
	}

	if nameSym, err := p.Lookup("Name"); err == nil {
		if name, ok := nameSym.(*string); ok {
			info.Name = *name
		}
	}

	if versionSym, err := p.Lookup("Version"); err == nil {
		if version, ok := versionSym.(*string); ok {
			info.Version = *version
		}
	}

	if descSym, err := p.Lookup("Description"); err == nil {
		if desc, ok := descSym.(*string); ok {
			info.Description = *desc
		}
	}

	if authorSym, err := p.Lookup("Author"); err == nil {
		if author, ok := authorSym.(*string); ok {
			info.Author = *author
		}
	}

	return info
}

func (l *Loader) Load(info *PluginInfo) bool {
	if _, exists := l.loaded[info.Name]; exists {
		return true
	}
	l.loaded[info.Name] = info
	return true
}

func (l *Loader) GetLoaded() map[string]*PluginInfo {
	result := make(map[string]*PluginInfo)
	for k, v := range l.loaded {
		result[k] = v
	}
	return result
}

type Manager struct {
	Loader   *Loader
	plugins  map[string]*PluginInfo
	Commands any
	Hooks    *HookRegistry
	Adapters any
}

func NewManager() *Manager {
	return &Manager{
		Loader:  NewLoader(),
		plugins: make(map[string]*PluginInfo),
		Hooks:   NewHookRegistry(),
	}
}

func (m *Manager) DiscoverAndLoad() int {
	discovered := m.Loader.Discover()
	loaded := 0

	for _, p := range discovered {
		if m.Loader.Load(p) {
			m.plugins[p.Name] = p
			m.setupPlugin(p)
			loaded++
		}
	}

	return loaded
}

func (m *Manager) setupPlugin(p *PluginInfo) {
	if p.Module == nil {
		return
	}

	setupSym, err := p.Module.Lookup("Setup")
	if err != nil {
		return
	}

	if setupFn, ok := setupSym.(func(*Manager)); ok {
		setupFn(m)
	}
}

func (m *Manager) LoadPlugin(path string) *PluginInfo {
	info := m.Loader.loadPluginInfo(path)
	if info == nil {
		return nil
	}

	if m.Loader.Load(info) {
		m.plugins[info.Name] = info
		m.setupPlugin(info)
		return info
	}

	return nil
}

func (m *Manager) GetPlugin(name string) *PluginInfo {
	return m.plugins[name]
}

func (m *Manager) ListPlugins() []*PluginInfo {
	result := make([]*PluginInfo, 0, len(m.plugins))
	for _, p := range m.plugins {
		result = append(result, p)
	}
	return result
}

func (m *Manager) UnloadPlugin(name string) bool {
	p, exists := m.plugins[name]
	if !exists {
		return false
	}

	if p.Module != nil {
		teardownSym, err := p.Module.Lookup("Teardown")
		if err == nil {
			if teardownFn, ok := teardownSym.(func(*Manager)); ok {
				teardownFn(m)
			}
		}
	}

	delete(m.plugins, name)
	return true
}
