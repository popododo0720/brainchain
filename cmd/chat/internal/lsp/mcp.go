package lsp

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
)

type MCPServer struct {
	tools  *Tools
	reader *bufio.Reader
	writer io.Writer
}

type mcpRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      any             `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type mcpResponse struct {
	JSONRPC string     `json:"jsonrpc"`
	ID      any        `json:"id,omitempty"`
	Result  any        `json:"result,omitempty"`
	Error   *mcpError  `json:"error,omitempty"`
}

type mcpError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

func NewMCPServer(workspaceRoot string) *MCPServer {
	return &MCPServer{
		tools:  NewTools(workspaceRoot),
		reader: bufio.NewReader(os.Stdin),
		writer: os.Stdout,
	}
}

func (s *MCPServer) Run() error {
	for {
		line, err := s.reader.ReadString('\n')
		if err != nil {
			if err == io.EOF {
				return nil
			}
			return err
		}

		var req mcpRequest
		if err := json.Unmarshal([]byte(line), &req); err != nil {
			s.sendError(nil, -32700, "Parse error")
			continue
		}

		s.handleRequest(&req)
	}
}

func (s *MCPServer) handleRequest(req *mcpRequest) {
	switch req.Method {
	case "initialize":
		s.sendResult(req.ID, map[string]any{
			"protocolVersion": "2024-11-05",
			"serverInfo": map[string]any{
				"name":    "brainchain-lsp",
				"version": "1.0.0",
			},
			"capabilities": map[string]any{
				"tools": map[string]any{},
			},
		})

	case "notifications/initialized":
		return

	case "tools/list":
		s.sendResult(req.ID, map[string]any{
			"tools": s.tools.GetToolDefinitions(),
		})

	case "tools/call":
		var params struct {
			Name      string         `json:"name"`
			Arguments map[string]any `json:"arguments"`
		}
		if err := json.Unmarshal(req.Params, &params); err != nil {
			s.sendError(req.ID, -32602, "Invalid params")
			return
		}

		result := s.tools.Execute(params.Name, params.Arguments)
		if !result.Success {
			s.sendResult(req.ID, map[string]any{
				"content": []map[string]any{
					{"type": "text", "text": fmt.Sprintf("Error: %s", result.Error)},
				},
				"isError": true,
			})
			return
		}

		output, _ := json.MarshalIndent(result.Data, "", "  ")
		s.sendResult(req.ID, map[string]any{
			"content": []map[string]any{
				{"type": "text", "text": string(output)},
			},
		})

	default:
		s.sendError(req.ID, -32601, fmt.Sprintf("Method not found: %s", req.Method))
	}
}

func (s *MCPServer) sendResult(id any, result any) {
	resp := mcpResponse{
		JSONRPC: "2.0",
		ID:      id,
		Result:  result,
	}
	s.send(resp)
}

func (s *MCPServer) sendError(id any, code int, message string) {
	resp := mcpResponse{
		JSONRPC: "2.0",
		ID:      id,
		Error:   &mcpError{Code: code, Message: message},
	}
	s.send(resp)
}

func (s *MCPServer) send(resp mcpResponse) {
	data, _ := json.Marshal(resp)
	fmt.Fprintln(s.writer, string(data))
}

func (s *MCPServer) Close() {
	if s.tools != nil {
		s.tools.Close()
	}
}
