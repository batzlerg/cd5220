#!/usr/bin/env python3

import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd

TELEMETRY_DIR = Path('generated_animations/telemetry')
EVENTS_FILE = TELEMETRY_DIR / 'events.jsonl'
TRAINING_FILE = TELEMETRY_DIR / 'training.jsonl'


def load_events():
    if not EVENTS_FILE.exists():
        print(f"Error: {EVENTS_FILE} not found")
        print(f"Have you run the VFD agent with telemetry enabled yet?")
        return pd.DataFrame()

    try:
        df = pd.read_json(EVENTS_FILE, lines=True)
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        print(f"Error loading events: {e}")
        return pd.DataFrame()


def summary():
    df = load_events()
    if df.empty:
        return "No data available"

    if 'datetime' not in df.columns:
        return "Invalid data format"

    df['date'] = df['datetime'].dt.date

    summary_df = df.groupby('date').agg({
        'success': ['count', 'sum', 'mean'],
        'attempt': ['mean'] if 'attempt' in df.columns else ['count']
    }).round(2)

    return summary_df


def pattern_performance():
    df = load_events()
    if df.empty:
        return "No data available"

    if 'spatial_patterns' not in df.columns:
        return "No pattern data available"

    df_success = df[df['success'] == True]

    if df_success.empty:
        return "No successful generations yet"

    pattern_data = []
    for idx, row in df_success.iterrows():
        patterns = row.get('spatial_patterns', [])
        if isinstance(patterns, list):
            pattern_str = ', '.join(patterns) if patterns else 'unknown'
        else:
            pattern_str = str(patterns)
        pattern_data.append({
            'patterns': pattern_str,
            'char_variety': row.get('unique_chars_count', 0),
            'width': row.get('estimated_width_percent', 0)
        })

    if not pattern_data:
        return "No pattern data"

    pattern_df = pd.DataFrame(pattern_data)
    result = pattern_df.groupby('patterns').agg({
        'char_variety': 'mean',
        'width': 'mean'
    }).round(1)

    result.columns = ['avg_char_variety', 'avg_width_coverage']
    result = result.sort_values('avg_char_variety', ascending=False)

    return result


def recent_failures(n=10):
    df = load_events()
    if df.empty:
        return "No data available"

    failures = df[df['success'] == False].tail(n)

    if failures.empty:
        return "No failures found (great!)"

    cols = ['datetime', 'idea', 'attempt']
    cols = [c for c in cols if c in failures.columns]

    return failures[cols]


def success_rate_trend(days=7):
    df = load_events()
    if df.empty:
        return "No data available"

    if 'datetime' not in df.columns:
        return "Invalid data format"

    cutoff = datetime.now() - pd.Timedelta(days=days)
    df_recent = df[df['datetime'] >= cutoff]

    if df_recent.empty:
        return f"No data in last {days} days"

    df_recent['date'] = df_recent['datetime'].dt.date
    trend_df = df_recent.groupby('date').agg({
        'success': ['count', 'mean']
    }).round(3)

    trend_df.columns = ['attempts', 'success_rate']
    trend_df['success_rate'] = (trend_df['success_rate'] * 100).round(1)

    return trend_df


def export_training_data(output_file=None, min_variety=5):
    if output_file is None:
        output_file = Path('generated_animations/exports/training_refined.jsonl')
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not TRAINING_FILE.exists():
        print(f"Error: {TRAINING_FILE} not found")
        return 0

    training_records = []
    with open(TRAINING_FILE, 'r') as f:
        for line in f:
            try:
                record = json.loads(line)
                training_records.append(record)
            except:
                continue

    if not training_records:
        print("No training data available")
        return 0

    filtered = []
    for record in training_records:
        metadata = record.get('metadata', {})
        variety = metadata.get('unique_chars_count', 0)

        if variety >= min_variety:
            filtered.append({
                'prompt': record.get('prompt', ''),
                'response': record.get('response', ''),
                'metadata': metadata
            })

    with open(output_file, 'w') as f:
        for record in filtered:
            f.write(json.dumps(record) + '\n')

    print(f"Exported {len(filtered)} high-quality examples to {output_file}")
    return len(filtered)


def bookmarks():
    """Show all bookmarked animations with analytics"""
    df = load_events()
    if df.empty:
        return "No data available"

    # Filter to bookmark events
    bookmarks_df = df[df['message'] == 'bookmark'].copy()

    if bookmarks_df.empty:
        return "No bookmarks yet. Press 'b' during playback to bookmark animations."

    # Join with generation events to get metrics
    generations = df[df['message'] == 'generation'].copy()
    if not generations.empty:
        gen_cols = generations[['generation_id', 'unique_chars_count']].copy()
        bookmarks_df = bookmarks_df.merge(gen_cols, on='generation_id', how='left', suffixes=('_bm', '_gen'))

        # Use the generation's unique_chars_count
        if 'unique_chars_count_gen' in bookmarks_df.columns:
            bookmarks_df['unique_chars_count'] = bookmarks_df['unique_chars_count_gen']
            bookmarks_df = bookmarks_df.drop(columns=['unique_chars_count_bm', 'unique_chars_count_gen'], errors='ignore')

    # Prepare display columns
    display_cols = ['datetime', 'generation_id', 'idea', 'unique_chars_count']
    display_cols = [c for c in display_cols if c in bookmarks_df.columns]

    result = bookmarks_df[display_cols].sort_values('datetime', ascending=False)

    # Add summary statistics
    print(f"Total bookmarks: {len(bookmarks_df)}")
    if 'unique_chars_count' in bookmarks_df.columns:
        avg_variety = bookmarks_df['unique_chars_count'].mean()
        print(f"Avg character variety: {avg_variety:.1f}")
    if 'spatial_patterns' in bookmarks_df.columns:
        pattern_counts = {}
        for patterns in bookmarks_df['spatial_patterns']:
            if isinstance(patterns, list):
                for p in patterns:
                    pattern_counts[p] = pattern_counts.get(p, 0) + 1
        if pattern_counts:
            top_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            pattern_str = ', '.join(f'{p}({c})' for p, c in top_patterns)
            print(f"Top patterns: {pattern_str}")
    print()

    return result


def downvotes():  # ★ NEW
    """Show all downvoted animations"""
    df = load_events()
    if df.empty:
        return "No data available"

    downvotes_df = df[df['message'] == 'downvote'].copy()

    if downvotes_df.empty:
        return "No downvotes recorded. Press 'd' during playback to downvote animations."

    display_cols = ['datetime', 'generation_id', 'idea']
    display_cols = [c for c in display_cols if c in downvotes_df.columns]

    result = downvotes_df[display_cols].sort_values('datetime', ascending=False)

    print(f"Total downvotes: {len(downvotes_df)}")

    if 'idea' in downvotes_df.columns:
        print(f"\nMost downvoted ideas:")
        idea_counts = downvotes_df.groupby('idea').size().sort_values(ascending=False)
        print(idea_counts.head(10))

    print()
    return result


def ratings():  # ★ NEW
    """Compare bookmarks vs downvotes for net ratings"""
    df = load_events()
    if df.empty:
        return "No data available"

    bookmarks_df = df[df['message'] == 'bookmark']
    downvotes_df = df[df['message'] == 'downvote']

    print(f"Total bookmarks: {len(bookmarks_df)}")
    print(f"Total downvotes: {len(downvotes_df)}")

    if bookmarks_df.empty and downvotes_df.empty:
        return "\nNo ratings data yet."

    print(f"\nNet positive animations:")

    all_ideas = list(set(bookmarks_df['idea'].tolist() + downvotes_df['idea'].tolist()))
    ratings = []
    for idea in all_ideas:
        up = len(bookmarks_df[bookmarks_df['idea'] == idea])
        down = len(downvotes_df[downvotes_df['idea'] == idea])
        net = up - down
        if net > 0:
            ratings.append((idea, up, down, net))

    ratings.sort(key=lambda x: x[3], reverse=True)
    for idea, up, down, net in ratings[:15]:
        print(f"  {idea:40s} +{up} -{down} (net: +{net})")

    return ""


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze.py <command>")
        print("\nCommands:")
        print("  summary              - Daily generation summary")
        print("  patterns             - Pattern performance stats")
        print("  failures [n]         - Recent failures (default: 10)")
        print("  trend [days]         - Success rate trend (default: 7 days)")
        print("  export [min_variety] - Export training data (default: min 5)")
        print("  bookmarks            - Show bookmarked animations")
        print("  downvotes            - Show downvoted animations")
        print("  ratings              - Compare bookmarks vs downvotes")
        return

    command = sys.argv[1]

    if command == 'summary':
        print("\n=== Daily Summary ===")
        print(summary())

    elif command == 'patterns':
        print("\n=== Pattern Performance ===")
        print(pattern_performance())

    elif command == 'failures':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        print(f"\n=== Recent Failures (last {n}) ===")
        print(recent_failures(n))

    elif command == 'trend':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        print(f"\n=== Success Rate Trend (last {days} days) ===")
        print(success_rate_trend(days))

    elif command == 'export':
        min_variety = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        export_training_data(min_variety=min_variety)

    elif command == 'bookmarks':
        print("\n=== Bookmarked Animations ===")
        print(bookmarks())

    elif command == 'downvotes':  # ★ NEW
        print("\n=== Downvoted Animations ===")
        print(downvotes())

    elif command == 'ratings':  # ★ NEW
        print("\n=== Animation Ratings Summary ===")
        print(ratings())

    else:
        print(f"Unknown command: {command}")
        print("Run without arguments to see available commands")


if __name__ == '__main__':
    main()
