package lsp

import (
	"encoding/json"
	"fmt"
	"path/filepath"
	"strings"
)

type ToolResult struct {
	Success bool   `json:"success"`
	Data    any    `json:"data,omitempty"`
	Error   string `json:"error,omitempty"`
}

type Tools struct {
	manager *Manager
}

func NewTools(workspaceRoot string) *Tools {
	return &Tools{
		manager: NewManager(workspaceRoot, ""),
	}
}

func (t *Tools) Close() {
	if t.manager != nil {
		t.manager.StopAll()
	}
}

func (t *Tools) Execute(toolName string, params map[string]any) ToolResult {
	switch toolName {
	case "lsp_goto_definition":
		return t.gotoDefinition(params)
	case "lsp_find_references":
		return t.findReferences(params)
	case "lsp_hover":
		return t.hover(params)
	case "lsp_diagnostics":
		return t.diagnostics(params)
	case "lsp_rename":
		return t.rename(params)
	case "lsp_prepare_rename":
		return t.prepareRename(params)
	case "lsp_document_symbols":
		return t.documentSymbols(params)
	case "lsp_workspace_symbols":
		return t.workspaceSymbols(params)
	case "lsp_status":
		return t.status(params)
	default:
		return ToolResult{Success: false, Error: fmt.Sprintf("unknown tool: %s", toolName)}
	}
}

func (t *Tools) gotoDefinition(params map[string]any) ToolResult {
	filePath, line, char, err := extractPosition(params)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	locations, err := t.manager.Definition(filePath, line, char)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	return ToolResult{Success: true, Data: formatLocations(locations)}
}

func (t *Tools) findReferences(params map[string]any) ToolResult {
	filePath, line, char, err := extractPosition(params)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	includeDecl := true
	if v, ok := params["includeDeclaration"].(bool); ok {
		includeDecl = v
	}

	locations, err := t.manager.References(filePath, line, char, includeDecl)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	return ToolResult{Success: true, Data: formatLocations(locations)}
}

func (t *Tools) hover(params map[string]any) ToolResult {
	filePath, line, char, err := extractPosition(params)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	result, err := t.manager.Hover(filePath, line, char)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	if result == nil {
		return ToolResult{Success: true, Data: nil}
	}

	return ToolResult{Success: true, Data: map[string]any{
		"contents": result.Contents,
		"range":    result.Range,
	}}
}

func (t *Tools) diagnostics(params map[string]any) ToolResult {
	filePath, ok := params["filePath"].(string)
	if !ok || filePath == "" {
		return ToolResult{Success: false, Error: "filePath is required"}
	}

	diags, err := t.manager.Diagnostics(filePath)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	return ToolResult{Success: true, Data: formatDiagnostics(diags)}
}

func (t *Tools) rename(params map[string]any) ToolResult {
	filePath, line, char, err := extractPosition(params)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	newName, ok := params["newName"].(string)
	if !ok || newName == "" {
		return ToolResult{Success: false, Error: "newName is required"}
	}

	edit, err := t.manager.Rename(filePath, line, char, newName)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	return ToolResult{Success: true, Data: formatWorkspaceEdit(edit)}
}

func (t *Tools) prepareRename(params map[string]any) ToolResult {
	filePath, line, char, err := extractPosition(params)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	r, err := t.manager.PrepareRename(filePath, line, char)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	if r == nil {
		return ToolResult{Success: false, Error: "rename not available at this position"}
	}

	return ToolResult{Success: true, Data: map[string]any{
		"start": map[string]int{"line": r.Start.Line, "character": r.Start.Character},
		"end":   map[string]int{"line": r.End.Line, "character": r.End.Character},
	}}
}

func (t *Tools) documentSymbols(params map[string]any) ToolResult {
	filePath, ok := params["filePath"].(string)
	if !ok || filePath == "" {
		return ToolResult{Success: false, Error: "filePath is required"}
	}

	symbols, err := t.manager.DocumentSymbols(filePath)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	return ToolResult{Success: true, Data: formatSymbols(symbols)}
}

func (t *Tools) workspaceSymbols(params map[string]any) ToolResult {
	query, _ := params["query"].(string)
	serverName, _ := params["server"].(string)

	if serverName == "" {
		serverName = "go"
	}

	symbols, err := t.manager.WorkspaceSymbols(serverName, query)
	if err != nil {
		return ToolResult{Success: false, Error: err.Error()}
	}

	return ToolResult{Success: true, Data: formatSymbols(symbols)}
}

func (t *Tools) status(params map[string]any) ToolResult {
	active := t.manager.ListActive()
	available := t.manager.ListAvailable()
	configured := t.manager.ListConfigured()

	return ToolResult{Success: true, Data: map[string]any{
		"active":     active,
		"available":  available,
		"configured": configured,
	}}
}

func extractPosition(params map[string]any) (string, int, int, error) {
	filePath, ok := params["filePath"].(string)
	if !ok || filePath == "" {
		return "", 0, 0, fmt.Errorf("filePath is required")
	}

	line, ok := params["line"].(float64)
	if !ok {
		if lineInt, ok := params["line"].(int); ok {
			line = float64(lineInt)
		} else {
			return "", 0, 0, fmt.Errorf("line is required (number)")
		}
	}

	char, ok := params["character"].(float64)
	if !ok {
		if charInt, ok := params["character"].(int); ok {
			char = float64(charInt)
		} else {
			return "", 0, 0, fmt.Errorf("character is required (number)")
		}
	}

	return filePath, int(line), int(char), nil
}

func formatLocations(locations []Location) []map[string]any {
	result := make([]map[string]any, len(locations))
	for i, loc := range locations {
		uri := loc.URI
		if strings.HasPrefix(uri, "file://") {
			uri = uri[7:]
		}
		result[i] = map[string]any{
			"file":  uri,
			"line":  loc.Range.Start.Line + 1,
			"col":   loc.Range.Start.Character + 1,
			"range": formatRange(loc.Range),
		}
	}
	return result
}

func formatRange(r Range) map[string]any {
	return map[string]any{
		"start": map[string]int{"line": r.Start.Line + 1, "character": r.Start.Character + 1},
		"end":   map[string]int{"line": r.End.Line + 1, "character": r.End.Character + 1},
	}
}

func formatDiagnostics(diags []Diagnostic) []map[string]any {
	severityNames := map[int]string{1: "error", 2: "warning", 3: "info", 4: "hint"}
	result := make([]map[string]any, len(diags))
	for i, d := range diags {
		sev := severityNames[d.Severity]
		if sev == "" {
			sev = "unknown"
		}
		result[i] = map[string]any{
			"severity": sev,
			"message":  d.Message,
			"source":   d.Source,
			"range":    formatRange(d.Range),
		}
	}
	return result
}

func formatWorkspaceEdit(edit *WorkspaceEdit) map[string]any {
	if edit == nil || edit.Changes == nil {
		return map[string]any{"changes": nil}
	}

	changes := make(map[string][]map[string]any)
	for uri, edits := range edit.Changes {
		path := uri
		if strings.HasPrefix(path, "file://") {
			path = path[7:]
		}
		changes[path] = make([]map[string]any, len(edits))
		for i, e := range edits {
			changes[path][i] = map[string]any{
				"range":   formatRange(e.Range),
				"newText": e.NewText,
			}
		}
	}
	return map[string]any{"changes": changes}
}

var symbolKindNames = map[int]string{
	1: "File", 2: "Module", 3: "Namespace", 4: "Package", 5: "Class",
	6: "Method", 7: "Property", 8: "Field", 9: "Constructor", 10: "Enum",
	11: "Interface", 12: "Function", 13: "Variable", 14: "Constant",
	15: "String", 16: "Number", 17: "Boolean", 18: "Array", 19: "Object",
	20: "Key", 21: "Null", 22: "EnumMember", 23: "Struct", 24: "Event",
	25: "Operator", 26: "TypeParameter",
}

func formatSymbols(symbols []Symbol) []map[string]any {
	result := make([]map[string]any, len(symbols))
	for i, s := range symbols {
		kind := symbolKindNames[s.Kind]
		if kind == "" {
			kind = "Unknown"
		}

		uri := s.Location.URI
		if strings.HasPrefix(uri, "file://") {
			uri = uri[7:]
		}

		result[i] = map[string]any{
			"name":      s.Name,
			"kind":      kind,
			"file":      uri,
			"line":      s.Location.Range.Start.Line + 1,
			"container": s.ContainerName,
		}
	}
	return result
}

func (t *Tools) GetToolDefinitions() []map[string]any {
	return []map[string]any{
		{
			"name":        "lsp_goto_definition",
			"description": "Jump to the definition of a symbol at the given position",
			"inputSchema": map[string]any{
				"type":     "object",
				"required": []string{"filePath", "line", "character"},
				"properties": map[string]any{
					"filePath":  map[string]any{"type": "string", "description": "Path to the file"},
					"line":      map[string]any{"type": "number", "description": "Line number (1-indexed)"},
					"character": map[string]any{"type": "number", "description": "Character position (1-indexed)"},
				},
			},
		},
		{
			"name":        "lsp_find_references",
			"description": "Find all references to a symbol at the given position",
			"inputSchema": map[string]any{
				"type":     "object",
				"required": []string{"filePath", "line", "character"},
				"properties": map[string]any{
					"filePath":           map[string]any{"type": "string", "description": "Path to the file"},
					"line":               map[string]any{"type": "number", "description": "Line number (1-indexed)"},
					"character":          map[string]any{"type": "number", "description": "Character position (1-indexed)"},
					"includeDeclaration": map[string]any{"type": "boolean", "description": "Include declaration in results"},
				},
			},
		},
		{
			"name":        "lsp_hover",
			"description": "Get hover information (type info, docs) at the given position",
			"inputSchema": map[string]any{
				"type":     "object",
				"required": []string{"filePath", "line", "character"},
				"properties": map[string]any{
					"filePath":  map[string]any{"type": "string", "description": "Path to the file"},
					"line":      map[string]any{"type": "number", "description": "Line number (1-indexed)"},
					"character": map[string]any{"type": "number", "description": "Character position (1-indexed)"},
				},
			},
		},
		{
			"name":        "lsp_diagnostics",
			"description": "Get diagnostics (errors, warnings) for a file",
			"inputSchema": map[string]any{
				"type":     "object",
				"required": []string{"filePath"},
				"properties": map[string]any{
					"filePath": map[string]any{"type": "string", "description": "Path to the file"},
				},
			},
		},
		{
			"name":        "lsp_rename",
			"description": "Rename a symbol at the given position across the workspace",
			"inputSchema": map[string]any{
				"type":     "object",
				"required": []string{"filePath", "line", "character", "newName"},
				"properties": map[string]any{
					"filePath":  map[string]any{"type": "string", "description": "Path to the file"},
					"line":      map[string]any{"type": "number", "description": "Line number (1-indexed)"},
					"character": map[string]any{"type": "number", "description": "Character position (1-indexed)"},
					"newName":   map[string]any{"type": "string", "description": "New name for the symbol"},
				},
			},
		},
		{
			"name":        "lsp_prepare_rename",
			"description": "Check if rename is valid at the given position",
			"inputSchema": map[string]any{
				"type":     "object",
				"required": []string{"filePath", "line", "character"},
				"properties": map[string]any{
					"filePath":  map[string]any{"type": "string", "description": "Path to the file"},
					"line":      map[string]any{"type": "number", "description": "Line number (1-indexed)"},
					"character": map[string]any{"type": "number", "description": "Character position (1-indexed)"},
				},
			},
		},
		{
			"name":        "lsp_document_symbols",
			"description": "Get all symbols (functions, classes, etc.) in a document",
			"inputSchema": map[string]any{
				"type":     "object",
				"required": []string{"filePath"},
				"properties": map[string]any{
					"filePath": map[string]any{"type": "string", "description": "Path to the file"},
				},
			},
		},
		{
			"name":        "lsp_workspace_symbols",
			"description": "Search for symbols across the workspace",
			"inputSchema": map[string]any{
				"type":     "object",
				"required": []string{"query"},
				"properties": map[string]any{
					"query":  map[string]any{"type": "string", "description": "Search query"},
					"server": map[string]any{"type": "string", "description": "LSP server name (e.g., 'go', 'typescript')"},
				},
			},
		},
		{
			"name":        "lsp_status",
			"description": "Get status of LSP servers (active, available, configured)",
			"inputSchema": map[string]any{
				"type":       "object",
				"properties": map[string]any{},
			},
		},
	}
}

func (t *Tools) ToJSON(result ToolResult) string {
	data, _ := json.Marshal(result)
	return string(data)
}

func (t *Tools) GetManager() *Manager {
	return t.manager
}

func GetFileLanguage(filePath string) string {
	ext := strings.ToLower(filepath.Ext(filePath))
	langMap := map[string]string{
		".go":   "go",
		".py":   "python",
		".rs":   "rust",
		".ts":   "typescript",
		".tsx":  "typescriptreact",
		".js":   "javascript",
		".jsx":  "javascriptreact",
		".c":    "c",
		".cpp":  "cpp",
		".cc":   "cpp",
		".h":    "c",
		".hpp":  "cpp",
		".json": "json",
		".yaml": "yaml",
		".yml":  "yaml",
	}
	if lang, ok := langMap[ext]; ok {
		return lang
	}
	return ""
}
