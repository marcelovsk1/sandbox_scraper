import json
import re
from selenium import webdriver
from bs4 import BeautifulSoup
import time
from datetime import datetime
from geopy.geocoders import Nominatim

def scroll_to_bottom(driver, max_scroll=10):
    for _ in range(max_scroll):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

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

def get_location_details(latitude, longitude):
    try:
        geolocator = Nominatim(user_agent="event_scraper")
        location = geolocator.reverse((latitude, longitude), exactly_one=True)
        if location:
            address = location.address
            city = location.raw.get('address', {}).get('city')
            country_code = location.raw.get('address', {}).get('country_code')

            # Ajustando a cidade para 'Montréal' e o código do país para 'ca' se a cidade for Montreal
            if city and city.lower() == 'montreal':
                city = 'Montréal'
                country_code = 'ca'

            return address, city, country_code
        else:
            return None, None, None
    except Exception as e:
        print(f"An error occurred while fetching location details: {e}")
        return None, None, None

def scrape_facebook_events(driver, url, selectors, max_scroll=10):
    driver.get(url)
    driver.implicitly_wait(30)

    all_events = []
    unique_event_titles = set()

    # Rolar para baixo para carregar mais eventos em lotes menores
    for _ in range(max_scroll):
        scroll_to_bottom(driver)
        time.sleep(5)  # Adicionar uma pausa entre os lotes de rolagem

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
                if any(event_title == existing_title for existing_title in unique_event_titles):
                    continue
            else:
                continue  # Skip this event if title element is not found

            location_div = event_page.find('div', class_='x1i10hfl xjbqb8w x1ejq31n xd10rxx x1sy0etr x17r0tee x972fbf xcfux6l x1qhh985 xm0m39n x9f619 x1ypdohk xt0psk2 xe8uvvx xdj266r x11i5rnm xat24cr x1mh8g0r xexx8yu x4uap5 x18d9i69 xkhd6sd x16tdsg8 x1hl2dhg xggy1nq x1a2a7pz xt0b8zv xzsf02u x1s688f')
            location_span = event_page.find('span', class_='xt0psk2')

            location_text = location_div.text.strip() if location_div else (location_span.text.strip() if location_span else None)

            latitude, longitude = get_coordinates(location_text)

            google_maps_url = open_google_maps(latitude, longitude)

            address_span = event_page.find('span', class_='x193iq5w xeuugli x13faqbe x1vvkbs xlh3980 xvmahel x1n0sxbx x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x x4zkp8e x3x7a5m x1f6kntn xvq8zen xo1l8bm xi81zsa x1yc453h')
            address = address_span.text.strip() if address_span else None

            location_details = {
                'Location': {
                    'Location': location_text,
                    'Address': address,
                    'Latitude': latitude,
                    'Longitude': longitude,
                    'GoogleMaps_URL': google_maps_url,
                    'City': None,
                    'CountryCode': None
                }
            }

            address, city, country_code = get_location_details(latitude, longitude)

            location_details['Location']['Address'] = address
            location_details['Location']['City'] = city
            location_details['Location']['CountryCode'] = country_code

            date_text = event_page.find('div', class_='x1e56ztr x1xmf6yo').text.strip() if event_page.find('div', class_='x1e56ztr x1xmf6yo') else None

            match = re.search(r'(\d{1,2}:\d{2}\s?[AP]M)\s?–\s?(\d{1,2}:\d{2}\s?[AP]M)', date_text)
            if match:
                start_time, end_time = match.groups()
            else:
                if "at" in date_text.lower():
                    start_time = re.search(r'(\d{1,2}:\d{2}\s?[AP]M)', date_text).group(1)
                    end_time = None
                else:
                    start_time, end_time = None, None

            event_info = {
                'Title': event_title,
                'Description': event_page.find('div', class_='xdj266r x11i5rnm xat24cr x1mh8g0r x1vvkbs').text.strip() if event_page.find('div', class_='xdj266r x11i5rnm xat24cr x1mh8g0r x1vvkbs') else None,
                'Date': date_text,
                **location_details,
                'ImageURL': event_page.find('img', class_='xz74otr x1ey2m1c x9f619 xds687c x5yr21d x10l6tqk x17qophe x13vifvy xh8yej3')['src'] if event_page.find('img', class_='xz74otr x1ey2m1c x9f619 xds687c x5yr21d x10l6tqk x17qophe x13vifvy xh8yej3') else None,
                'Organizer': event_page.find('span', class_='xt0psk2').text.strip() if event_page.find('span', class_='xt0psk2') else None,
                'Organizer_IMG': event_page.find('img', class_='xz74otr')['src'] if event_page.find('img', class_='xz74otr') else None,
                'EventUrl': event_url,
                'StartTime': start_time,
                'EndTime': end_time
            }

            all_events.append(event_info)
            unique_event_titles.add(event_title)

            driver.back()

    return all_events

if __name__ == "__main__":
    sources = [
        {
            'name': 'Facebook',
            'url': 'https://www.facebook.com/events/explore/montreal-quebec/102184499823699/',
            'selectors': {
                'event': {'tag': 'div', 'class': 'x78zum5 x1n2onr6 xh8yej3'}
            },
        }
    ]

    driver = webdriver.Chrome()

    all_events = []
    for source in sources:
        print(f"Scraping events from: {source['name']}")
        if source['name'] == 'Facebook':
            events = scrape_facebook_events(driver, source['url'], source['selectors'])
            # Convertendo objetos Tag em strings e verificando se a chave 'Div' está presente
            for event in events:
                if 'Div' in event['Location']:
                    event['Location']['Div'] = str(event['Location']['Div'])
                if 'Span' in event['Location']:
                    event['Location']['Span'] = str(event['Location']['Span'])
            all_events.extend(events)
        elif source['name'] == 'Eventbrite':
            events = scrape_eventbrite_events(driver, source['url'], source['selectors'])
            all_events.extend(events)
        else:
            print(f"Unsupported source: {source['name']}")
            continue

    with open('facebookkkkk.json', 'w') as f:
        json.dump(all_events, f, indent=4)

    driver.quit()
