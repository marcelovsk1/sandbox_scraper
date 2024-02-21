import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
from fuzzywuzzy import fuzz
from datetime import datetime
import requests
from geopy.geocoders import Nominatim
import time
import geopy.exc

def scroll_to_bottom(driver, max_clicks=5):
    for _ in range(max_clicks):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

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
    if source == 'Facebook' or source == 'Eventbrite':
        return {
            'Location': location_str.strip(),
        }
    elif source == 'Google':
        # Use Google Places API to get formatted location and additional information
        api_key = 'AIzaSyD4K3294QGT9YUSquGZ_G82YMI856E0BzA'
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
    retries = 3  # Number of retries
    delay = 2  # Delay between retries in seconds

    for _ in range(retries):
        try:
            location = geolocator.geocode(location)
            if location:
                return location.latitude, location.longitude
            else:
                return None, None
        except geopy.exc.GeocoderUnavailable as e:
            print(f"Geocoding service unavailable: {e}")
            print(f"Retrying after {delay} seconds...")
            time.sleep(delay)

    print(f"Unable to geocode location: {location}")
    return None, None

def scrape_eventbrite_events(driver, url, selectors, max_pages=5):
    driver.get(url)
    driver.implicitly_wait(10)

    all_events = []

    for _ in range(max_pages):
        page_content = driver.page_source
        webpage = BeautifulSoup(page_content, 'html.parser')
        events = webpage.find_all(selectors['event']['tag'], class_=selectors['event'].get('class'))

        for event in events:
            event_info = {}
            for key, selector in selectors.items():
                if key != 'event':
                    element = event.find(selector['tag'], class_=selector.get('class'))
                    event_info[key] = element.text.strip() if element else None
                    if key == 'ImageURL':
                        event_info[key] = element['src'] if element and 'src' in element.attrs else None

            event_link = event.find('a', href=True)['href']
            driver.get(event_link)

            event_page_content = driver.page_source
            event_page = BeautifulSoup(event_page_content, 'html.parser')

            title = event_page.find('h1', class_='event-title css-0').text.strip() if event_page.find('h1', class_='event-title css-0') else None
            description = event_page.find('p', class_='summary').text.strip() if event_page.find('p', class_='summary') else None
            price = event_page.find('div', class_='conversion-bar__panel-info').text.strip() if event_page.find('div', class_='conversion-bar__panel-info') else None
            date = event_page.find('span', class_='date-info__full-datetime').text.strip() if event_page.find('span', class_='date-info__full-datetime') else None
            location_element = event_page.find('p', class_='location-info__address-text')
            location = location_element.text.strip() if location_element else None

            # Obtenha as coordenadas de latitude e longitude
            latitude, longitude = get_coordinates(location)

            tags_elements = event_page.find_all('li', class_='tags-item inline')

            tags = []
            for tag_element in tags_elements:
                tag_link = tag_element.find('a')
                if tag_link:
                    tag_text = tag_link.text.strip().replace("#", "")  # Remove o caractere "#" do início do texto
                    tags.append(tag_text)

            event_info['Tags'] = tags

            organizer = event_page.find('a', class_='descriptive-organizer-info__name-link') if event_page.find('a', class_='descriptive-organizer-info__name-link') else None
            image_url_organizer = event_page.find('svg', class_='eds-avatar__background eds-avatar__background--has-border')
            if image_url_organizer:
                image_tag = image_url_organizer.find('image')
                if image_tag:
                    event_info['Image URL Organizer'] = image_tag.get('xlink:href')
                else:
                    event_info['Image URL Organizer'] = None
            else:
                event_info['Image URL Organizer'] = None

            event_info['Title'] = title
            event_info['Description'] = description
            event_info['Price'] = price
            event_info['Date'] = date
            event_info['Location'] = location
            event_info['Latitude'] = latitude  # Adiciona latitude
            event_info['Longitude'] = longitude  # Adiciona longitude
            event_info['Tags'] = tags
            event_info['Organizer'] = organizer.text.strip() if organizer else None
            event_info['EventUrl'] = event_link  # Adiciona o EventUrl ao dicionário

            # Adicione a URL do Google Maps para o evento
            if latitude is not None and longitude is not None:
                map_url = f"https://maps.googleapis.com/maps/api/staticmap?center={latitude},{longitude}&zoom=13&size=400x300&maptype=roadmap&markers=color:red%7Clabel:C%7C{latitude},{longitude}&key=YOUR_API_KEY"
                event_info['MapURL'] = map_url

            all_events.append(event_info)

            driver.back()

        try:
            next_button = driver.find_element_by_link_text('Next')
            next_button.click()
        except:
            break

    return all_events

def main():
    sources = [
        {
            'name': 'Eventbrite',
            'url': 'https://www.eventbrite.com/d/canada--montreal/all-events/',
            'selectors': {
                'event': {'tag': 'div', 'class': 'discover-search-desktop-card discover-search-desktop-card--hiddeable'},
                'Title': {'tag': 'h2', 'class': 'event-card__title'},
                'Description': {'tag': 'p', 'class': 'event-card__description'},
                'Date': {'tag': 'p', 'class': 'event-card__date'},
                'Location': {'tag': 'p', 'class': 'location-info__address-text'},
                'Price': {'tag': 'p', 'class': 'event-card__price'},
                'ImageURL': {'tag': 'img', 'class': 'event-card__image'},
                'Tags': {'tag': 'ul', 'class': 'event-card__tags'},
                'Organizer': {'tag': 'a', 'class': 'event-card__organizer'},
                'Organizer_IMG': {'tag': 'svg', 'class': 'eds-avatar__background eds-avatar__background--has-border'}
            },
            'max_pages': 20
        }
    ]

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)

    all_events = []
    for source in sources:
        print(f"Scraping events from: {source['name']}")
        if source['name'] == 'Eventbrite':
            events = scrape_eventbrite_events(driver, source['url'], source['selectors'])
        else:
            print(f"Unsupported source: {source['name']}")
            continue
        all_events.extend(events)

    # Salvar eventos únicos em um arquivo JSON
    with open('eventbrite.json', 'w') as f:
        json.dump(all_events, f, indent=4)

    driver.quit()

if __name__ == "__main__":
    main()
