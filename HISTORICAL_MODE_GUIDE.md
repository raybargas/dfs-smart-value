# Historical Mode Guide

This guide explains how to use the Historical Mode feature to run roster builds using past week's data for testing and analysis.

## Overview

Historical Mode allows you to:
- Switch between current and historical analysis
- Select specific NFL weeks for analysis
- View data availability for each week
- Fetch and cache historical data
- Run complete roster builds using past week's data

## How to Use Historical Mode

### 1. Enable Historical Mode

1. Open the DFS Lineup Optimizer
2. Look for the **🕰️ Analysis Mode** section in the sidebar
3. Toggle **Historical Mode** to enable historical analysis
4. Select the week you want to analyze

### 2. Select Historical Week

When Historical Mode is enabled:
- Use the week selector to choose any NFL week (1-18)
- The system will show data availability for that week
- Click **🔄 Load Week Data** to load the selected week's data

### 3. View Data Status

The system shows:
- **✅ Complete**: Both Vegas lines and injury data available
- **⚠️ Partial**: Only one type of data available
- **❌ No Data**: No data available for that week

### 4. Data Management

Use the **📊 Data Management** section to:
- View all available historical weeks
- Save current week data to cache
- Load weeks from cache
- See data completeness for each week

## Fetching Historical Data

### Using the UI

1. Go to **📊 Narrative Intelligence** page
2. Use the **🔄 Refresh Vegas Lines** and **🔄 Refresh Injury Reports** buttons
3. The system will fetch data for the currently selected week
4. Data is automatically saved to the database and cache

### Using the Command Line

Use the `fetch_historical_data.py` script to fetch multiple weeks:

```bash
# Fetch data for weeks 1, 2, and 3
python3 fetch_historical_data.py --weeks 1 2 3

# Fetch data for a single week
python3 fetch_historical_data.py --weeks 5

# Use custom API key
python3 fetch_historical_data.py --weeks 1 2 3 --api-key YOUR_API_KEY
```

### Environment Variables

Set these environment variables for API access:

```bash
# For Vegas lines (The Odds API)
export THE_ODDS_API_KEY="your_odds_api_key"

# For injury reports (ESPN - no key required)
# ESPN API is free and doesn't require authentication
```

## Workflow Examples

### Example 1: Test Week 5 Strategy

1. Enable Historical Mode
2. Select Week 5
3. Load Week 5 data
4. Upload Week 5 player data (CSV/Excel)
5. Run through the complete workflow:
   - Narrative Intelligence
   - Player Selection
   - Optimization
   - Lineup Generation
   - Results

### Example 2: Compare Multiple Weeks

1. Fetch data for weeks 4, 5, and 6
2. For each week:
   - Enable Historical Mode
   - Select the week
   - Run the complete workflow
   - Compare results across weeks

### Example 3: Backtesting Strategy

1. Fetch historical data for multiple weeks
2. Use the same optimization settings
3. Run builds for each week
4. Analyze performance across different weeks
5. Identify patterns and optimize strategy

## Data Storage

### Database Tables

- **`vegas_lines`**: Stores Vegas odds and implied team totals
- **`injury_reports`**: Stores player injury status and details
- Both tables use weekly overwrite (no duplicates)

### Cache Files

- **`data/cache/vegas_lines_weekX.json`**: Cached Vegas data
- **`data/cache/injury_reports_weekX.json`**: Cached injury data
- Cache files enable quick loading of historical data

## Troubleshooting

### No Data Available

If a week shows "No Data Available":
1. Check if you have the required API keys
2. Use the fetch buttons to get fresh data
3. Verify the week number is correct (1-18)

### Partial Data

If only partial data is available:
1. Check API key validity
2. Verify internet connection
3. Try fetching again

### Cache Issues

If cache loading fails:
1. Check file permissions
2. Verify cache files exist
3. Re-fetch data from APIs

## Best Practices

### Data Management

1. **Fetch Early**: Get historical data when APIs are available
2. **Cache Everything**: Save data to cache for quick access
3. **Verify Completeness**: Check that both Vegas and injury data are available
4. **Regular Updates**: Keep historical data current

### Analysis Workflow

1. **Start with Data**: Ensure you have complete data for the target week
2. **Use Consistent Settings**: Keep optimization settings the same across weeks
3. **Document Results**: Record findings for each week
4. **Compare Patterns**: Look for trends across multiple weeks

### Performance Tips

1. **Use Cache**: Load from cache instead of re-fetching from APIs
2. **Batch Operations**: Fetch multiple weeks at once
3. **Offline Analysis**: Once data is cached, you can work offline
4. **Efficient Storage**: The system uses weekly overwrite to prevent duplicates

## API Limits

### The Odds API
- **Free Tier**: 500 requests/month
- **Paid Tiers**: Higher limits available
- **Rate Limits**: 1 request/second

### ESPN API
- **Free**: No authentication required
- **Rate Limits**: Reasonable limits, no official documentation
- **Reliability**: Generally stable but unofficial

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Verify API keys and internet connection
3. Check the console for error messages
4. Ensure you have the latest version of the application

## Future Enhancements

Planned improvements:
- **Automated Fetching**: Schedule automatic data fetching
- **Data Validation**: Enhanced data quality checks
- **Performance Metrics**: Track historical performance
- **Export Features**: Export historical analysis results
- **Visualization**: Charts and graphs for historical trends
