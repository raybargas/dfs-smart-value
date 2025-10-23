# Weekly Update Guide

## Updating the Default NFL Week

**Single Source of Truth:** All default week settings are controlled by one variable in `config.py`.

### Steps to Update Each Week

1. Open `DFS/config.py`
2. Find the line: `DEFAULT_NFL_WEEK = 8`
3. Update the number to the current NFL week
4. Commit and push the change

That's it! The entire app will automatically use the new default week.

### Example

```python
# config.py
DEFAULT_NFL_WEEK = 9  # Update this for Week 9
```

### What Gets Updated Automatically

When you change `DEFAULT_NFL_WEEK`, the following are automatically updated:

- ✅ Week selector default in Data Ingestion page
- ✅ Session state initialization in main app
- ✅ All fallback defaults throughout the app
- ✅ Historical data loading
- ✅ Season stats file naming
- ✅ Database queries

### User Override

Users can always manually change the week using the dropdown selector. The config only sets the **default** for new sessions.

### Other Configuration

The `config.py` file also contains other app-wide settings:

- **Season Configuration**: `CURRENT_SEASON`, `SEASON_LABEL`
- **DFS Site**: `DEFAULT_SITE`
- **Week Range**: `MIN_WEEK`, `MAX_WEEK`
- **Database**: `DEFAULT_DB_PATH`
- **Optimization**: `DEFAULT_LINEUP_COUNT`, `MAX_LINEUP_COUNT`
- **File Upload**: `MAX_FILE_SIZE_MB`, `ALLOWED_FILE_TYPES`

### Benefits of This Approach

1. **Single Source of Truth**: One place to update, no hunting through code
2. **Consistency**: Guaranteed consistency across the entire app
3. **Maintainability**: Easy to update weekly
4. **Documentation**: Clear configuration file with comments
5. **Type Safety**: Import errors caught immediately if config is missing

