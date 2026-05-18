"""
Garmin uses the 7-bit GSM character set for SMS with a capacity of 160 characters per message.

For each time period we encode:
 - WMO Weather Interpretation Code (5 bits)
 - Mid-level clouds, 12.5% increments (3 bits)
 - Precip chance, 12.5% increments (3 bits)
 - Snow accumulation, 1in increments (4 bits)
 - Freezing level, 1000ft increments (4 bits)
 - For each altitude level (700, 500, 450 hPa):
    - Wind gust, 5mph increments (5 bits)
    - Wind direction, 8 directions (3 bits)

In total that is 43 bits per time period. With 160 * 7 = 1120 bits per message, we can fit 26 time periods per message.
"""
