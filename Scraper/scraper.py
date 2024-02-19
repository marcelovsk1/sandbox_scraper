import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
from fuzzywuzzy import fuzz
from datetime import datetime

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
    #%A: Represents the full name of the day of the week (for example, "Sunday").
    #%B: Represents the full name of the month (for example, "March").
    #%d: Represents the day of the month as a decimal number (for example, "03").
    #%Y: Represents the four-digit year (for example, "2024").

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
    else:
        return None


def scrape_facebook_events(driver, url, selectors, max_scroll=50):
    driver.get(url)
    driver.implicitly_wait(10)

    all_events = []
    unique_event_urls = set()

    for _ in range(max_scroll):
        page_content = driver.page_source
        webpage = BeautifulSoup(page_content, 'html.parser')
        events = webpage.find_all(selectors['event']['tag'], class_=selectors['event'].get('class'))

        for event in events:
            event_link = event.find('a', href=True)
            if not event_link:
                continue

            event_url = 'https://www.facebook.com' + event_link['href'] if event_link['href'].startswith('/') else event_link['href']
            if event_url in unique_event_urls:
                continue

            driver.get(event_url)
            time.sleep(1)

            event_page_content = driver.page_source
            event_page = BeautifulSoup(event_page_content, 'html.parser')

            location_div = event_page.find('div', class_='x1i10hfl xjbqb8w x1ejq31n xd10rxx x1sy0etr x17r0tee x972fbf xcfux6l x1qhh985 xm0m39n x9f619 x1ypdohk xt0psk2 xe8uvvx xdj266r x11i5rnm xat24cr x1mh8g0r xexx8yu x4uap5 x18d9i69 xkhd6sd x16tdsg8 x1hl2dhg xggy1nq x1a2a7pz xt0b8zv xzsf02u x1s688f')
            location_span = event_page.find('span', class_='xt0psk2')

            location_text = location_div.text.strip() if location_div else (location_span.text.strip() if location_span else None)

            event_info = {
                'Title': event_page.find('span', class_='x1lliihq x6ikm8r x10wlt62 x1n2onr6').text.strip(),
                'Description': event_page.find('div', class_='xdj266r x11i5rnm xat24cr x1mh8g0r x1vvkbs').text.strip(),
                'Date': event_page.find('div', class_='x1e56ztr x1xmf6yo').text.strip() if event_page.find('div', class_='x1e56ztr x1xmf6yo') else None,
                'Location': location_text,
                'ImageURL': event_page.find('img', class_='xz74otr x1ey2m1c x9f619 xds687c x5yr21d x10l6tqk x17qophe x13vifvy xh8yej3')['src'] if event_page.find('img', class_='xz74otr x1ey2m1c x9f619 xds687c x5yr21d x10l6tqk x17qophe x13vifvy xh8yej3') else None,
                'Organizer': event_page.find('span', class_='xt0psk2').text.strip() if event_page.find('span', class_='xt0psk2') else None,
                'Organizer_IMG': event_page.find('img', class_='xz74otr')['src'] if event_page.find('img', class_='xz74otr') else None,
                'EventUrl': event_url
            }

            all_events.append(event_info)
            unique_event_urls.add(event_url)

            driver.back()

        scroll_to_bottom(driver)

    return all_events



def get_previous_page_image_url(driver):
    url = 'https://www.eventbrite.com/d/canada--montreal/all-events/?page=1'

    driver.get(url)

    if driver.page_source:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        img_tag = soup.find('img', class_='event-card-image')

        if img_tag:
            return img_tag['src']

    return None

def scrape_eventbrite_events(driver, url, selectors, max_pages=10):
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
            location_element = event_page.find('div', class_='location-info__address')
            location = location_element.text.strip() if location_element else None
            ImageURL = get_previous_page_image_url(driver)
            tags_elements = event_page.find_all('li', class_='tags-item inline')

            tags = []
            for tag_element in tags_elements:
                tag_link = tag_element.find('a')
                if tag_link:
                    tags.append(tag_link.text.strip())

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
            event_info['ImageURL'] = ImageURL
            event_info['Tags'] = tags
            event_info['Organizer'] = organizer.text.strip() if organizer else None
            event_info['EventUrl'] = event_link  # Adiciona o EventUrl ao dicionário


            all_events.append(event_info)

            driver.back()

        try:
            next_button = driver.find_element_by_link_text('Next')
            next_button.click()
        except:
            break

    return all_events

def find_unique_events(events):
    unique_events = []
    seen_event_info = set()
    for event in events:
        formatted_date = format_date(event.get('Date', ''), event.get('Source', ''))
        formatted_location = format_location(event.get('Location', ''), event.get('Source', ''))
        event_info = (event['Title'], formatted_date, formatted_location)
        if event_info not in seen_event_info:
            unique_events.append(event)
            seen_event_info.add(event_info)
    return unique_events

def main():
    sources = [
        {
            'name': 'Facebook',
            'url': 'https://www.facebook.com/events/explore/montreal-quebec/102184499823699/',
            'selectors': {
                'event': {'tag': 'div', 'class': 'x78zum5 x1n2onr6 xh8yej3'}
            },
        },
        {
            'name': 'Eventbrite',
            'url': 'https://www.eventbrite.com/d/canada--montreal/all-events/',
                'selectors': {
                    'event': {'tag': 'div', 'class': 'discover-search-desktop-card discover-search-desktop-card--hiddeable'},
                    'Title': {'tag': 'h2', 'class': 'event-card__title'},
                    'Description': {'tag': 'p', 'class': 'event-card__description'},
                    'Date': {'tag': 'p', 'class': 'event-card__date'},
                    'Location': {'tag': 'p', 'class': 'event-card__location'},
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
        if source['name'] == 'Facebook':
            events = scrape_facebook_events(driver, source['url'], source['selectors'])
        elif source['name'] == 'Eventbrite':
            events = scrape_eventbrite_events(driver, source['url'], source['selectors'])
        else:
            print(f"Unsupported source: {source['name']}")
            continue
        all_events.extend(events)

    # Find unique events
    unique_events = find_unique_events(all_events)

    # Save unique events to JSON file
    with open('unique_events.json', 'w') as f:
        json.dump(unique_events, f, indent=4)

    driver.quit()

if __name__ == "__main__":
    main()
