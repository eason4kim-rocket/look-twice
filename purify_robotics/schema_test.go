package purifyrobotics

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestPublishedSchemasAreValidJSONWithUniqueIDs(t *testing.T) {
	paths, err := filepath.Glob(filepath.Join("..", "schemas", "*.schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	if len(paths) < 8 {
		t.Fatalf("expected at least 8 published schemas, found %d", len(paths))
	}
	seenIDs := map[string]string{}
	for _, path := range paths {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		var document map[string]any
		if err := json.Unmarshal(data, &document); err != nil {
			t.Fatalf("%s is not valid JSON: %v", path, err)
		}
		id, ok := document["$id"].(string)
		if !ok || id == "" {
			t.Fatalf("%s has no non-empty $id", path)
		}
		if previous, exists := seenIDs[id]; exists {
			t.Fatalf("duplicate schema $id %q in %s and %s", id, previous, path)
		}
		seenIDs[id] = path
	}
}
