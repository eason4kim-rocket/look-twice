// purify-robotics-core is a persistent NDJSON service for the contest-only
// Purify Robotics Reference Core. It writes protocol responses only to stdout.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	core "github.com/eason4kim-rocket/look-twice/purify_robotics"
)

func main() {
	scanner := bufio.NewScanner(os.Stdin)
	buffer := make([]byte, 64*1024)
	scanner.Buffer(buffer, 16*1024*1024)
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetEscapeHTML(false)
	for scanner.Scan() {
		response := core.ProcessLine(scanner.Bytes())
		if err := encoder.Encode(response); err != nil {
			fmt.Fprintf(os.Stderr, "encode response: %v\n", err)
			os.Exit(1)
		}
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "read NDJSON: %v\n", err)
		os.Exit(1)
	}
}
