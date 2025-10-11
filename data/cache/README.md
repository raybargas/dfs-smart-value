# API Data Cache

This directory stores cached API responses as JSON files, allowing the app to:
- **Load instantly** without API calls on every visit
- **Share data** across all users (committed to Git)
- **Reduce API usage** and avoid rate limits
- **Work offline** when cache is available

## Cache Files

Cache files are named: `{data_type}_week{number}.json`

Examples:
- `vegas_lines_week6.json` - Week 6 Vegas odds/lines
- `injury_reports_week6.json` - Week 6 injury reports

## How It Works

1. **First Load**: App tries to load from cache files
2. **Cache Miss**: If no cache exists, fetches from APIs
3. **Auto-Save**: Fresh API data is automatically saved to cache
4. **Manual Refresh**: Use "Refresh from APIs" button to update cache

## Committing Cache Files

When you refresh data from APIs, the cache files are updated locally.

**To share updated data with all users:**
```bash
cd DFS
git add data/cache/*.json
git commit -m "Update cached Vegas lines and injury reports for Week X"
git push origin main
```

This way, all users get the updated data without making their own API calls!

## File Size

Each cache file is typically:
- Vegas lines: ~5-15 KB (16 games/week)
- Injury reports: ~10-50 KB (varies by injuries)

Total cache size per week: **~20-70 KB** (very git-friendly!)

