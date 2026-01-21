package lsp

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"sync/atomic"
	"time"
)

type Position struct {
	Line      int `json:"line"`
	Character int `json:"character"`
}

type Range struct {
	Start Position `json:"start"`
	End   Position `json:"end"`
}

type Location struct {
	URI   string `json:"uri"`
	Range Range  `json:"range"`
}

type Diagnostic struct {
	Range    Range  `json:"range"`
	Message  string `json:"message"`
	Severity int    `json:"severity"`
	Source   string `json:"source,omitempty"`
	Code     any    `json:"code,omitempty"`
}

type TextEdit struct {
	Range   Range  `json:"range"`
	NewText string `json:"newText"`
}

type WorkspaceEdit struct {
	Changes map[string][]TextEdit `json:"changes"`
}

type Client struct {
	config        *ServerConfig
	workspaceRoot string
	timeout       time.Duration
	connected     bool
	process       *exec.Cmd
	stdin         io.WriteCloser
	stdout        *bufio.Reader
	requestID     atomic.Int64
	pending       map[int64]chan json.RawMessage
	pendingMu     sync.Mutex
	ctx           context.Context
	cancel        context.CancelFunc
}

func NewClient(config *ServerConfig, workspaceRoot string, timeout time.Duration) *Client {
	if workspaceRoot == "" {
		workspaceRoot, _ = os.Getwd()
	}
	if timeout == 0 {
		timeout = 30 * time.Second
	}
	ctx, cancel := context.WithCancel(context.Background())
	return &Client{
		config:        config,
		workspaceRoot: workspaceRoot,
		timeout:       timeout,
		pending:       make(map[int64]chan json.RawMessage),
		ctx:           ctx,
		cancel:        cancel,
	}
}

func (c *Client) IsConnected() bool {
	return c.connected
}

func (c *Client) Connect() error {
	if len(c.config.Command) == 0 {
		return fmt.Errorf("no command specified")
	}

	c.process = exec.CommandContext(c.ctx, c.config.Command[0], c.config.Command[1:]...)
	c.process.Dir = c.workspaceRoot

	var err error
	c.stdin, err = c.process.StdinPipe()
	if err != nil {
		return fmt.Errorf("stdin pipe: %w", err)
	}

	stdout, err := c.process.StdoutPipe()
	if err != nil {
		return fmt.Errorf("stdout pipe: %w", err)
	}
	c.stdout = bufio.NewReader(stdout)

	if err := c.process.Start(); err != nil {
		return fmt.Errorf("start process: %w", err)
	}

	go c.readResponses()

	if err := c.initialize(); err != nil {
		c.Disconnect()
		return fmt.Errorf("initialize: %w", err)
	}

	c.connected = true
	return nil
}

func (c *Client) Disconnect() {
	c.connected = false
	c.cancel()
	if c.stdin != nil {
		c.stdin.Close()
	}
	if c.process != nil && c.process.Process != nil {
		c.process.Process.Kill()
	}
}

func (c *Client) nextID() int64 {
	return c.requestID.Add(1)
}

func (c *Client) sendRequest(method string, params any) (json.RawMessage, error) {
	id := c.nextID()
	req := map[string]any{
		"jsonrpc": "2.0",
		"id":      id,
		"method":  method,
		"params":  params,
	}

	data, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	respChan := make(chan json.RawMessage, 1)
	c.pendingMu.Lock()
	c.pending[id] = respChan
	c.pendingMu.Unlock()

	defer func() {
		c.pendingMu.Lock()
		delete(c.pending, id)
		c.pendingMu.Unlock()
	}()

	header := fmt.Sprintf("Content-Length: %d\r\n\r\n", len(data))
	if _, err := c.stdin.Write([]byte(header)); err != nil {
		return nil, err
	}
	if _, err := c.stdin.Write(data); err != nil {
		return nil, err
	}

	select {
	case resp := <-respChan:
		return resp, nil
	case <-time.After(c.timeout):
		return nil, fmt.Errorf("request timeout")
	case <-c.ctx.Done():
		return nil, c.ctx.Err()
	}
}

func (c *Client) sendNotification(method string, params any) error {
	req := map[string]any{
		"jsonrpc": "2.0",
		"method":  method,
		"params":  params,
	}

	data, err := json.Marshal(req)
	if err != nil {
		return err
	}

	header := fmt.Sprintf("Content-Length: %d\r\n\r\n", len(data))
	if _, err := c.stdin.Write([]byte(header)); err != nil {
		return err
	}
	if _, err := c.stdin.Write(data); err != nil {
		return err
	}
	return nil
}

func (c *Client) readResponses() {
	for {
		select {
		case <-c.ctx.Done():
			return
		default:
		}

		var contentLength int
		for {
			line, err := c.stdout.ReadString('\n')
			if err != nil {
				return
			}
			if line == "\r\n" {
				break
			}
			fmt.Sscanf(line, "Content-Length: %d", &contentLength)
		}

		if contentLength == 0 {
			continue
		}

		data := make([]byte, contentLength)
		if _, err := io.ReadFull(c.stdout, data); err != nil {
			return
		}

		var resp struct {
			ID     *int64          `json:"id"`
			Result json.RawMessage `json:"result"`
			Error  *struct {
				Code    int    `json:"code"`
				Message string `json:"message"`
			} `json:"error"`
		}

		if err := json.Unmarshal(data, &resp); err != nil {
			continue
		}

		if resp.ID != nil {
			c.pendingMu.Lock()
			if ch, ok := c.pending[*resp.ID]; ok {
				ch <- resp.Result
			}
			c.pendingMu.Unlock()
		}
	}
}

func (c *Client) initialize() error {
	absPath, _ := filepath.Abs(c.workspaceRoot)
	uri := "file://" + absPath

	params := map[string]any{
		"processId": os.Getpid(),
		"rootUri":   uri,
		"capabilities": map[string]any{
			"textDocument": map[string]any{
				"definition":    map[string]any{"dynamicRegistration": false},
				"references":    map[string]any{"dynamicRegistration": false},
				"rename":        map[string]any{"dynamicRegistration": false},
				"publishDiagnostics": map[string]any{"relatedInformation": true},
			},
		},
		"workspaceFolders": []map[string]any{
			{"uri": uri, "name": filepath.Base(c.workspaceRoot)},
		},
	}

	if len(c.config.InitOptions) > 0 {
		params["initializationOptions"] = c.config.InitOptions
	}

	_, err := c.sendRequest("initialize", params)
	if err != nil {
		return err
	}

	return c.sendNotification("initialized", map[string]any{})
}

func (c *Client) fileURI(path string) string {
	if !filepath.IsAbs(path) {
		path = filepath.Join(c.workspaceRoot, path)
	}
	return "file://" + path
}

func (c *Client) Definition(uri string, line, character int) ([]Location, error) {
	if !c.connected {
		return nil, fmt.Errorf("not connected")
	}

	if uri[:7] != "file://" {
		uri = c.fileURI(uri)
	}

	params := map[string]any{
		"textDocument": map[string]any{"uri": uri},
		"position":     map[string]any{"line": line, "character": character},
	}

	result, err := c.sendRequest("textDocument/definition", params)
	if err != nil {
		return nil, err
	}

	var locations []Location
	if err := json.Unmarshal(result, &locations); err != nil {
		var single Location
		if err := json.Unmarshal(result, &single); err == nil {
			locations = []Location{single}
		}
	}
	return locations, nil
}

func (c *Client) References(uri string, line, character int, includeDeclaration bool) ([]Location, error) {
	if !c.connected {
		return nil, fmt.Errorf("not connected")
	}

	if uri[:7] != "file://" {
		uri = c.fileURI(uri)
	}

	params := map[string]any{
		"textDocument": map[string]any{"uri": uri},
		"position":     map[string]any{"line": line, "character": character},
		"context":      map[string]any{"includeDeclaration": includeDeclaration},
	}

	result, err := c.sendRequest("textDocument/references", params)
	if err != nil {
		return nil, err
	}

	var locations []Location
	json.Unmarshal(result, &locations)
	return locations, nil
}

func (c *Client) Rename(uri string, line, character int, newName string) (*WorkspaceEdit, error) {
	if !c.connected {
		return nil, fmt.Errorf("not connected")
	}

	if uri[:7] != "file://" {
		uri = c.fileURI(uri)
	}

	params := map[string]any{
		"textDocument": map[string]any{"uri": uri},
		"position":     map[string]any{"line": line, "character": character},
		"newName":      newName,
	}

	result, err := c.sendRequest("textDocument/rename", params)
	if err != nil {
		return nil, err
	}

	var edit WorkspaceEdit
	json.Unmarshal(result, &edit)
	return &edit, nil
}

func (c *Client) Diagnostics(uri string) ([]Diagnostic, error) {
	if !c.connected {
		return nil, fmt.Errorf("not connected")
	}

	if uri[:7] != "file://" {
		uri = c.fileURI(uri)
	}

	params := map[string]any{
		"textDocument": map[string]any{"uri": uri},
	}

	result, err := c.sendRequest("textDocument/diagnostic", params)
	if err != nil {
		return nil, err
	}

	var resp struct {
		Items []Diagnostic `json:"items"`
	}
	json.Unmarshal(result, &resp)
	return resp.Items, nil
}

type HoverResult struct {
	Contents string `json:"contents"`
	Range    *Range `json:"range,omitempty"`
}

func (c *Client) Hover(uri string, line, character int) (*HoverResult, error) {
	if !c.connected {
		return nil, fmt.Errorf("not connected")
	}

	if len(uri) < 7 || uri[:7] != "file://" {
		uri = c.fileURI(uri)
	}

	params := map[string]any{
		"textDocument": map[string]any{"uri": uri},
		"position":     map[string]any{"line": line, "character": character},
	}

	result, err := c.sendRequest("textDocument/hover", params)
	if err != nil {
		return nil, err
	}

	if result == nil || string(result) == "null" {
		return nil, nil
	}

	var hover struct {
		Contents any    `json:"contents"`
		Range    *Range `json:"range,omitempty"`
	}
	if err := json.Unmarshal(result, &hover); err != nil {
		return nil, err
	}

	var contents string
	switch v := hover.Contents.(type) {
	case string:
		contents = v
	case map[string]any:
		if val, ok := v["value"].(string); ok {
			contents = val
		}
	case []any:
		for _, item := range v {
			if s, ok := item.(string); ok {
				contents += s + "\n"
			} else if m, ok := item.(map[string]any); ok {
				if val, ok := m["value"].(string); ok {
					contents += val + "\n"
				}
			}
		}
	}

	return &HoverResult{Contents: contents, Range: hover.Range}, nil
}

type Symbol struct {
	Name          string   `json:"name"`
	Kind          int      `json:"kind"`
	Location      Location `json:"location,omitempty"`
	ContainerName string   `json:"containerName,omitempty"`
}

func (c *Client) DocumentSymbols(uri string) ([]Symbol, error) {
	if !c.connected {
		return nil, fmt.Errorf("not connected")
	}

	if len(uri) < 7 || uri[:7] != "file://" {
		uri = c.fileURI(uri)
	}

	params := map[string]any{
		"textDocument": map[string]any{"uri": uri},
	}

	result, err := c.sendRequest("textDocument/documentSymbol", params)
	if err != nil {
		return nil, err
	}

	var symbols []Symbol
	json.Unmarshal(result, &symbols)
	return symbols, nil
}

func (c *Client) WorkspaceSymbols(query string) ([]Symbol, error) {
	if !c.connected {
		return nil, fmt.Errorf("not connected")
	}

	params := map[string]any{
		"query": query,
	}

	result, err := c.sendRequest("workspace/symbol", params)
	if err != nil {
		return nil, err
	}

	var symbols []Symbol
	json.Unmarshal(result, &symbols)
	return symbols, nil
}

func (c *Client) PrepareRename(uri string, line, character int) (*Range, error) {
	if !c.connected {
		return nil, fmt.Errorf("not connected")
	}

	if len(uri) < 7 || uri[:7] != "file://" {
		uri = c.fileURI(uri)
	}

	params := map[string]any{
		"textDocument": map[string]any{"uri": uri},
		"position":     map[string]any{"line": line, "character": character},
	}

	result, err := c.sendRequest("textDocument/prepareRename", params)
	if err != nil {
		return nil, err
	}

	if result == nil || string(result) == "null" {
		return nil, nil
	}

	var r Range
	if err := json.Unmarshal(result, &r); err != nil {
		return nil, err
	}
	return &r, nil
}
