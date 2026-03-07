import json
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def fetch_iex_data():
    print("🤖 Booting headless browser...")
    
    # Set up Chrome to run silently in the background
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    # Extra safety flags to prevent background crashes
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Initialize the driver (this auto-downloads the correct Chrome version)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        print("🌐 Loading IEX Day-Ahead Market (Waiting 8 seconds for React to render)...")
        driver.get("https://www.iexindia.com/market-data/day-ahead-market/market-snapshot")
        
        # CRITICAL: Give Next.js time to render the RSC payload into an actual HTML table
        time.sleep(8) 
        
        # Hand the fully rendered HTML over to BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # ---------------------------------------------------------
        # PARSING THE MATERIAL-UI TABLE
        # ---------------------------------------------------------
        # 1. Find the main body of the table
        table_body = soup.find("tbody") 
        
        if not table_body:
            print("⚠️ Could not find the table body. The page might still be loading.")
            return

        # 2. Get all the rows
        rows = table_body.find_all("tr")
        print(f"📊 Found {len(rows)} rows of data. Extracting prices...")
        
        iex_prices_kwh = []
        for row in rows:
            cells = row.find_all("td")
            
            # Make sure this row actually has data columns
            if len(cells) >= 5: 
                try:
                    # The MCP price is the LAST column in the row (index -1)
                    mcp_text = cells[-1].text.replace(',', '').strip()
                    
                    # Convert to float and then to Rs/kWh
                    mcp_mwh = float(mcp_text)
                    mcp_kwh = mcp_mwh / 1000.0
                    iex_prices_kwh.append(round(mcp_kwh, 3))
                except ValueError:
                    # If it hits a weird cell or a header, skip it and keep going
                    continue

        # IEX gives 96 blocks (15-min intervals). Slice it down to 24 hours.
        # Taking every 4th element to get an hourly snapshot
        if len(iex_prices_kwh) >= 96:
            hourly_prices = iex_prices_kwh[::4][:24]
            
            # Save the fresh data to a JSON file so Streamlit can read it
            with open("live_grid_data.json", "w") as f:
                json.dump(hourly_prices, f)
            print("✅ Successfully scraped and saved 24-hour data to live_grid_data.json!")
            print(f"📈 Sample data: {hourly_prices[:5]}...")
            
        else:
            print(f"⚠️ Only found {len(iex_prices_kwh)} data points. Expected at least 96. Check your BeautifulSoup targeting.")

    except Exception as e:
        print(f"❌ Scraping failed: {e}")
    finally:
        driver.quit()
        print("🛑 Browser closed.")

if __name__ == "__main__":
    fetch_iex_data()