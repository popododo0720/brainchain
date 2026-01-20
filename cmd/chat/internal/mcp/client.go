package mcp

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os/exec"
	"sync"
	"sync/atomic"
	"time"
)

type Tool struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	InputSchema map[string]any `json:"inputSchema"`
	ServerName  string         `json:"serverName,omitempty"`
}

type ToolResult struct {
	Success    bool   `json:"success"`
	Content    any    `json:"content,omitempty"`
	Error      string `json:"error,omitempty"`
	DurationMs int64  `json:"durationMs"`
}

type Client struct {
	config    *ServerConfig
	name      string
	timeout   time.Duration
	connected bool
	process   *exec.Cmd
	stdin     io.WriteCloser
	stdout    *bufio.Reader
	requestID atomic.Int64
	pending   map[int64]chan json.RawMessage
	pendingMu sync.Mutex
	tools     []Tool
	ctx       context.Context
	cancel    context.CancelFunc
}

func NewClient(config *ServerConfig, timeout time.Duration) *Client {
	if timeout == 0 {
		timeout = time.Duration(config.Timeout) * time.Second
		if timeout == 0 {
			timeout = 30 * time.Second
		}
	}
	ctx, cancel := context.WithCancel(context.Background())
	return &Client{
		config:  config,
		name:    config.Name,
		timeout: timeout,
		pending: make(map[int64]chan json.RawMessage),
		ctx:     ctx,
		cancel:  cancel,
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

	if len(c.config.Env) > 0 {
		for k, v := range c.config.Env {
			c.process.Env = append(c.process.Env, fmt.Sprintf("%s=%s", k, v))
		}
	}

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

	tools, err := c.listToolsInternal()
	if err != nil {
		c.Disconnect()
		return fmt.Errorf("list tools: %w", err)
	}
	c.tools = tools

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
	c.tools = nil
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
	params := map[string]any{
		"protocolVersion": "2024-11-05",
		"capabilities":    map[string]any{},
		"clientInfo": map[string]any{
			"name":    "brainchain",
			"version": "1.0.0",
		},
	}

	_, err := c.sendRequest("initialize", params)
	return err
}

func (c *Client) listToolsInternal() ([]Tool, error) {
	result, err := c.sendRequest("tools/list", map[string]any{})
	if err != nil {
		return nil, err
	}

	var resp struct {
		Tools []struct {
			Name        string         `json:"name"`
			Description string         `json:"description"`
			InputSchema map[string]any `json:"inputSchema"`
		} `json:"tools"`
	}

	if err := json.Unmarshal(result, &resp); err != nil {
		return nil, err
	}

	tools := make([]Tool, len(resp.Tools))
	for i, t := range resp.Tools {
		tools[i] = Tool{
			Name:        t.Name,
			Description: t.Description,
			InputSchema: t.InputSchema,
			ServerName:  c.name,
		}
	}
	return tools, nil
}

func (c *Client) ListTools() []Tool {
	if !c.connected {
		return nil
	}
	result := make([]Tool, len(c.tools))
	copy(result, c.tools)
	return result
}

func (c *Client) CallTool(name string, arguments map[string]any) ToolResult {
	start := time.Now()

	if !c.connected {
		return ToolResult{
			Success:    false,
			Error:      "not connected",
			DurationMs: time.Since(start).Milliseconds(),
		}
	}

	params := map[string]any{
		"name":      name,
		"arguments": arguments,
	}

	result, err := c.sendRequest("tools/call", params)
	duration := time.Since(start).Milliseconds()

	if err != nil {
		return ToolResult{
			Success:    false,
			Error:      err.Error(),
			DurationMs: duration,
		}
	}

	var resp struct {
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
		IsError bool `json:"isError"`
	}

	if err := json.Unmarshal(result, &resp); err != nil {
		return ToolResult{
			Success:    false,
			Error:      err.Error(),
			DurationMs: duration,
		}
	}

	var content any
	if len(resp.Content) == 1 {
		content = resp.Content[0].Text
	} else if len(resp.Content) > 1 {
		texts := make([]string, len(resp.Content))
		for i, c := range resp.Content {
			texts[i] = c.Text
		}
		content = texts
	}

	return ToolResult{
		Success:    !resp.IsError,
		Content:    content,
		DurationMs: duration,
	}
}
