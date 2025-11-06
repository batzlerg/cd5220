#!/bin/bash
#
# inspect_frame_captures.sh
# Explores captured animation frames and displays their contents
#
# Usage:
#   ./inspect_frame_captures.sh                    # Show summary of all captures
#   ./inspect_frame_captures.sh [filename.jsonl]   # Show detailed view of specific file
#   ./inspect_frame_captures.sh --latest           # Show most recent capture
#

set -o pipefail

# Colors
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    DIM='\033[2m'
    RESET='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' DIM='' RESET=''
fi

# Configuration
CAPTURES_DIR="generated_animations/frame_captures"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Logging functions
log_header() {
    echo -e "\n${BOLD}========================================${RESET}"
    echo -e "${BOLD}$1${RESET}"
    echo -e "${BOLD}========================================${RESET}"
}

log_info() { echo -e "${BLUE}ℹ${RESET} $*"; }
log_ok() { echo -e "${GREEN}✓${RESET} $*"; }
log_warn() { echo -e "${YELLOW}⚠${RESET} $*"; }
log_error() { echo -e "${RED}✗${RESET} $*"; }
log_dim() { echo -e "${DIM}$*${RESET}"; }

# Check if captures directory exists
check_captures_dir() {
    if [[ ! -d "$CAPTURES_DIR" ]]; then
        log_error "Captures directory not found: $CAPTURES_DIR"
        log_info "Run vfd_agent.py with --preview or simulator mode to generate captures"
        exit 1
    fi
}

# Count captures
count_captures() {
    find "$CAPTURES_DIR" -name "*.jsonl" 2>/dev/null | wc -l
}

# Parse JSONL metadata
get_metadata() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        echo "{}"
        return
    fi
    head -1 "$file" | python3 -c "import sys, json; data = json.load(sys.stdin); print(json.dumps(data.get('_meta', {})))" 2>/dev/null || echo "{}"
}

# Parse JSONL frames
get_frame_count() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        echo "0"
        return
    fi
    echo $(($(wc -l < "$file") - 1))
}

# Get specific frame
get_frame() {
    local file="$1"
    local frame_num="$2"
    
    # Line number is frame_num + 2 (skip metadata line, 1-indexed)
    local line_num=$((frame_num + 2))
    
    sed -n "${line_num}p" "$file" 2>/dev/null
}

# Display frame visually
display_frame() {
    local frame_json="$1"
    local frame_num="$2"
    
    local line1=$(echo "$frame_json" | python3 -c "import sys, json; print(json.load(sys.stdin)['line1'])" 2>/dev/null)
    local line2=$(echo "$frame_json" | python3 -c "import sys, json; print(json.load(sys.stdin)['line2'])" 2>/dev/null)
    
    if [[ -z "$line1" ]]; then
        log_error "Failed to parse frame $frame_num"
        return
    fi
    
    echo -e "${DIM}--- Frame $frame_num ---${RESET}"
    echo -e "${CYAN}${line1}${RESET}"
    echo -e "${CYAN}${line2}${RESET}"
    echo -e "${DIM}--------------------${RESET}"
}

# Show summary of all captures
show_summary() {
    log_header "Frame Captures Summary"
    
    check_captures_dir
    
    local total=$(count_captures)
    
    if [[ $total -eq 0 ]]; then
        log_warn "No frame captures found in $CAPTURES_DIR"
        log_info "Generate captures by running:"
        log_info "  ./vfd_agent.py --preview --idea 'your animation idea'"
        return
    fi
    
    log_ok "Found $total frame capture(s) in $CAPTURES_DIR"
    echo ""
    
    # List all captures with metadata
    local count=0
    for capture_file in "$CAPTURES_DIR"/*.jsonl; do
        count=$((count + 1))
        local basename=$(basename "$capture_file")
        local metadata=$(get_metadata "$capture_file")
        local frame_count=$(get_frame_count "$capture_file")
        
        local anim_id=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin).get('animation_id', 'unknown'))" 2>/dev/null)
        local timestamp=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin).get('created_at', 'unknown'))" 2>/dev/null)
        local idea=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin).get('idea', 'N/A'))" 2>/dev/null)
        local is_validation=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin).get('validation', False))" 2>/dev/null)
        local is_playback=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin).get('playback', False))" 2>/dev/null)
        
        local type_label="unknown"
        if [[ "$is_validation" == "True" ]]; then
            type_label="${GREEN}validation${RESET}"
        elif [[ "$is_playback" == "True" ]]; then
            type_label="${CYAN}playback${RESET}"
        fi
        
        echo -e "${BOLD}$count.${RESET} ${YELLOW}$basename${RESET}"
        echo -e "   Animation ID: $anim_id"
        echo -e "   Frames: $frame_count"
        echo -e "   Type: $type_label"
        if [[ "$idea" != "N/A" ]]; then
            echo -e "   Idea: ${DIM}$idea${RESET}"
        fi
        echo -e "   Created: ${DIM}$timestamp${RESET}"
        echo ""
    done
    
    log_info "To inspect a specific capture:"
    log_info "  $0 [filename.jsonl]"
    log_info ""
    log_info "To view the latest capture:"
    log_info "  $0 --latest"
}

# Show detailed view of specific capture
show_detailed() {
    local capture_file="$1"
    
    # Handle relative paths
    if [[ ! -f "$capture_file" ]]; then
        capture_file="$CAPTURES_DIR/$capture_file"
    fi
    
    if [[ ! -f "$capture_file" ]]; then
        log_error "Capture file not found: $capture_file"
        exit 1
    fi
    
    log_header "Frame Capture Details"
    
    local basename=$(basename "$capture_file")
    log_info "File: ${YELLOW}$basename${RESET}"
    echo ""
    
    # Parse metadata
    local metadata=$(get_metadata "$capture_file")
    log_ok "Metadata:"
    echo "$metadata" | python3 -m json.tool 2>/dev/null | sed 's/^/  /'
    echo ""
    
    # Frame count
    local frame_count=$(get_frame_count "$capture_file")
    log_ok "Total frames: $frame_count"
    echo ""
    
    # Frame statistics
    log_info "Analyzing frame content..."
    python3 << EOFPYTHON
import json
import sys

frames = []
with open("$capture_file") as f:
    next(f)  # Skip metadata
    for line in f:
        frame = json.loads(line)
        frames.append((frame['line1'], frame['line2']))

non_empty = sum(1 for l1, l2 in frames if l1.strip() or l2.strip())
both_rows = sum(1 for l1, l2 in frames if l1.strip() and l2.strip())
total = len(frames)

print(f"  Non-empty frames: {non_empty}/{total} ({100*non_empty/total:.1f}%)")
print(f"  Both rows active: {both_rows}/{total} ({100*both_rows/total:.1f}%)")
print(f"  Empty frames: {total - non_empty}")
EOFPYTHON
    
    echo ""
    
    # Show sample frames
    log_header "Sample Frames"
    
    # Show first, middle, and last frames
    local middle=$((frame_count / 2))
    local last=$((frame_count - 1))
    
    if [[ $frame_count -gt 0 ]]; then
        log_info "First frame:"
        local frame0=$(get_frame "$capture_file" 0)
        display_frame "$frame0" 0
        echo ""
    fi
    
    if [[ $frame_count -gt 10 ]]; then
        log_info "Middle frame (${middle}):"
        local frame_mid=$(get_frame "$capture_file" $middle)
        display_frame "$frame_mid" $middle
        echo ""
    fi
    
    if [[ $frame_count -gt 1 ]]; then
        log_info "Last frame (${last}):"
        local frame_last=$(get_frame "$capture_file" $last)
        display_frame "$frame_last" $last
        echo ""
    fi
    
    # Offer to show all frames
    log_info "Commands:"
    log_info "  Show all frames:"
    log_dim "    cat $capture_file | tail -n +2 | python3 -c \"import sys, json; [print(f\\\"Frame {i}:\\\\n{json.loads(line)['line1']}\\\\n{json.loads(line)['line2']}\\\\n\\\") for i, line in enumerate(sys.stdin)]\""
    echo ""
    log_info "  Export as text:"
    log_dim "    $0 --export-text $basename output.txt"
}

# Export capture as readable text
export_as_text() {
    local capture_file="$1"
    local output_file="$2"
    
    if [[ ! -f "$capture_file" ]]; then
        capture_file="$CAPTURES_DIR/$capture_file"
    fi
    
    if [[ ! -f "$capture_file" ]]; then
        log_error "Capture file not found: $capture_file"
        exit 1
    fi
    
    log_info "Exporting $capture_file to $output_file..."
    
    python3 << EOFPYTHON
import json

with open("$capture_file") as f:
    metadata = json.loads(f.readline())['_meta']
    frames = [json.loads(line) for line in f]

with open("$output_file", 'w') as out:
    out.write("=" * 60 + "\n")
    out.write(f"Animation: {metadata.get('animation_id', 'unknown')}\n")
    out.write(f"Frames: {len(frames)}\n")
    if 'idea' in metadata:
        out.write(f"Idea: {metadata['idea']}\n")
    out.write("=" * 60 + "\n\n")
    
    for frame in frames:
        out.write(f"--- Frame {frame['frame']} ---\n")
        out.write(frame['line1'] + "\n")
        out.write(frame['line2'] + "\n")
        out.write("-" * 20 + "\n\n")

print(f"Exported {len(frames)} frames to $output_file")
EOFPYTHON
    
    log_ok "Exported to $output_file"
}

# Show latest capture
show_latest() {
    check_captures_dir
    
    local latest=$(ls -t "$CAPTURES_DIR"/*.jsonl 2>/dev/null | head -1)
    
    if [[ -z "$latest" ]]; then
        log_error "No captures found"
        exit 1
    fi
    
    log_info "Latest capture: $(basename "$latest")"
    echo ""
    show_detailed "$latest"
}

# Main logic
main() {
    cd "$SCRIPT_DIR" || exit 1
    
    if [[ $# -eq 0 ]]; then
        show_summary
        exit 0
    fi
    
    case "$1" in
        --latest|-l)
            show_latest
            ;;
        --export-text)
            if [[ $# -lt 3 ]]; then
                log_error "Usage: $0 --export-text [capture.jsonl] [output.txt]"
                exit 1
            fi
            export_as_text "$2" "$3"
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [FILE]"
            echo ""
            echo "Options:"
            echo "  (no args)           Show summary of all captures"
            echo "  --latest, -l        Show latest capture details"
            echo "  --export-text FILE  Export capture to text file"
            echo "  --help, -h          Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                                    # List all captures"
            echo "  $0 --latest                           # Show latest"
            echo "  $0 anim_1234_5678.jsonl              # Show specific capture"
            echo "  $0 --export-text anim_1234.jsonl out.txt"
            ;;
        *)
            show_detailed "$1"
            ;;
    esac
}

main "$@"
