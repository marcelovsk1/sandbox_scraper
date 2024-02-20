import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
from fuzzywuzzy import fuzz
from datetime import datetime
import requests
from geopy.geocoders import Nominatim
import webbrowser

def scroll_to_bottom(driver, max_scroll=5):
    for _ in range(max_scroll):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Esperar um tempo para a página carregar completamente

def calculate_similarity(str1, str2):
    return fuzz.token_sort_ratio(str1, str2)

def format_date(date_str, source):
    if date_str is None:
        return None

    date_str_lower = date_str.lower()
    source_lower = source.lower()

    if source_lower == 'facebook':
        # Facebook: SUNDAY, MARCH 3, 2024
        formatted_date = datetime.strptime(date_str, '%A, %B %d, %Y')
        return formatted_date
    elif source_lower == 'eventbrite':
        # Eventbrite: Sunday, March 3
        formatted_date = datetime.strptime(date_str, '%A, %B %d')
        return formatted_date
    else:
        return None

def format_location(location_str, source):
    if source == 'Facebook':
        # If location contains a comma, we split into location name and address
        if ',' in location_str:
            location, address = location_str.split(',', 1)
            return {
                'Location': location.strip(),
                'Address': address.strip()
            }
        else:
            # If there is no comma, we assume it is just the location name
            return {
                'Location': location_str.strip(),
            }
    elif source == 'Eventbrite':
        # Eventbrite already provides separate location and address
        return {
            'Location': location_str.strip(),
        }
    elif source == 'Google':
        # Use Google Places API to get formatted location and additional information
        api_key = 'YOUR_GOOGLE_API_KEY'
        url = f'https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={location_str}&inputtype=textquery&fields=formatted_address,geometry&key={api_key}'
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'OK' and len(data['candidates']) > 0:
                formatted_address = data['candidates'][0]['formatted_address']
                location = formatted_address.split(',')[0]  # Extracting the location name
                return {
                    'Location': location.strip(),
                    'FormattedAddress': formatted_address,
                    'Latitude': data['candidates'][0]['geometry']['location']['lat'],
                    'Longitude': data['candidates'][0]['geometry']['location']['lng']
                }
        # If unable to fetch data from Google Places API, return None
        return None
    else:
        return None

def get_coordinates(location):
    geolocator = Nominatim(user_agent="event_scraper")
    location = geolocator.geocode(location)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

def open_google_maps(latitude, longitude):
    google_maps_url = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
    return google_maps_url

def scrape_facebook_events(driver, url, selectors, max_scroll=5):
    driver.get(url)
    driver.implicitly_wait(20)

    all_events = []
    unique_event_titles = set()

    # Rolar para baixo para carregar mais eventos
    scroll_to_bottom(driver, max_scroll)

    page_content = driver.page_source
    webpage = BeautifulSoup(page_content, 'html.parser')
    events = webpage.find_all(selectors['event']['tag'], class_=selectors['event'].get('class'))

    for event in events:
        event_link = event.find('a', href=True)
        if not event_link:
            continue

        event_url = 'https://www.facebook.com' + event_link['href'] if event_link['href'].startswith('/') else event_link['href']

        driver.get(event_url)
        time.sleep(1)

        event_page_content = driver.page_source
        event_page = BeautifulSoup(event_page_content, 'html.parser')

        event_title_elem = event_page.find('span', class_='x1lliihq x6ikm8r x10wlt62 x1n2onr6')
        if event_title_elem:
            event_title = event_title_elem.text.strip()
            if any(calculate_similarity(event_title, existing_title) >= 90 for existing_title in unique_event_titles):
                continue
        else:
            continue  # Skip this event if title element is not found

        location_div = event_page.find('div', class_='x1i10hfl xjbqb8w x1ejq31n xd10rxx x1sy0etr x17r0tee x972fbf xcfux6l x1qhh985 xm0m39n x9f619 x1ypdohk xt0psk2 xe8uvvx xdj266r x11i5rnm xat24cr x1mh8g0r xexx8yu x4uap5 x18d9i69 xkhd6sd x16tdsg8 x1hl2dhg xggy1nq x1a2a7pz xt0b8zv xzsf02u x1s688f')
        location_span = event_page.find('span', class_='xt0psk2')

        location_text = location_div.text.strip() if location_div else (location_span.text.strip() if location_span else None)

        latitude, longitude = get_coordinates(location_text)

        # Abre o Google Maps com a localização do evento
        google_maps_url = open_google_maps(latitude, longitude)

        event_info = {
            'Title': event_title,
            'Description': event_page.find('div', class_='xdj266r x11i5rnm xat24cr x1mh8g0r x1vvkbs').text.strip() if event_page.find('div', class_='xdj266r x11i5rnm xat24cr x1mh8g0r x1vvkbs') else None,
            'Date': event_page.find('div', class_='x1e56ztr x1xmf6yo').text.strip() if event_page.find('div', class_='x1e56ztr x1xmf6yo') else None,
            'Location': location_text,
            'Latitude': latitude,
            'Longitude': longitude,
            'GoogleMaps_URL': google_maps_url,  # URL do Google Maps para a localização do evento
            'ImageURL': event_page.find('img', class_='xz74otr x1ey2m1c x9f619 xds687c x5yr21d x10l6tqk x17qophe x13vifvy xh8yej3')['src'] if event_page.find('img', class_='xz74otr x1ey2m1c x9f619 xds687c x5yr21d x10l6tqk x17qophe x13vifvy xh8yej3') else None,
            'Organizer': event_page.find('span', class_='xt0psk2').text.strip() if event_page.find('span', class_='xt0psk2') else None,
            'Organizer_IMG': event_page.find('img', class_='xz74otr')['src'] if event_page.find('img', class_='xz74otr') else None,
            'EventUrl': event_url
        }

        all_events.append(event_info)
        unique_event_titles.add(event_title)

        driver.back()

    return all_events

def main():
    sources = [
        {
            'name': 'Facebook',
            'url': 'https://www.facebook.com/events/explore/montreal-quebec/102184499823699/',
            'selectors': {
                'event': {'tag': 'div', 'class': 'x78zum5 x1n2onr6 xh8yej3'}
            },
        }
    ]

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)

    all_events = []
    for source in sources:
        print(f"Scraping events from: {source['name']}")
        if source['name'] == 'Facebook':
            events = scrape_facebook_events(driver, source['url'], source['selectors'])
        elif source['name'] == 'Eventbrite':
            events = scrape_eventbrite_events(driver, source['url'], source['selectors'])
        else:
            print(f"Unsupported source: {source['name']}")
            continue
        all_events.extend(events)

    # Save events to JSON file
    with open('facebook.json', 'w') as f:
        json.dump(all_events, f, indent=4)

    driver.quit()

if __name__ == "__main__":
    main()
