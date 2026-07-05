# Weather API Comparison

Comparison of free weather APIs for use in automated prompts and cron jobs.

## wttr.in

- URL: `https://wttr.in/{location}?format=%C+%t&lang=zh`
- Pro: No API key, simple, supports Chinese
- Con: Inconsistent for Chinese district-level locations (e.g., "Shushan" times out), limited to city-level

## Open-Meteo (RECOMMENDED)

- URL: `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=weather_code,temperature_2m,relative_humidity_2m,apparent_temperature&timezone=Asia/Shanghai`
- Pro: Free, no API key, coordinate-level precision, WMO weather codes, structured JSON
- Con: WMO codes need manual mapping to Chinese descriptions

### WMO Weather Code → Chinese Mapping

```python
wmo_desc = {
    0: "晴天", 1: "大部晴", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "中等阵雨", 82: "大阵雨",
    95: "雷暴", 96: "雷暴+小冰雹", 99: "雷暴+大冰雹",
}
```

### Example Usage

```python
import aiohttp

async def get_weather(lat=31.85, lon=117.25):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=weather_code,temperature_2m,relative_humidity_2m,apparent_temperature"
        f"&timezone=Asia/Shanghai"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json()
            c = data["current"]
            desc = wmo_desc.get(c["weather_code"], f"code{c['weather_code']}")
            return f"{desc} {c['temperature_2m']}°C，体感{c['apparent_temperature']}°C，湿度{c['relative_humidity_2m']}%"
```

### Precise Coordinates (Hefei)

For district-level precision:
- 蜀山区 (Shushan): 31.85, 117.25
- 庐阳区 (Luyang): 31.88, 117.26