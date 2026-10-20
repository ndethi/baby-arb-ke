"""
Robust marketplace scraping functions for eBay, Mercari, Facebook Marketplace, OfferUp.
Uses requests + BeautifulSoup to extract product links and prices.
"""
import re
import subprocess
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

def extract_price_from_text(text):
    """Extract the first price in $d.dd format from text."""
    if not text:
        return None
    match = re.search(r'\$(\d+(?:\.\d{2})?)', text)
    if match:
        try:
            price = float(match.group(1))
            if 2 <= price <= 1000:  # reasonable range for baby items
                return price
        except ValueError:
            pass
    return None

def is_product_link(url, marketplace):
    """Heuristic to check if a URL looks like a product listing link."""
    if not url:
        return False
    url_lower = url.lower()
    if marketplace == 'ebay':
        # eBay item links typically contain /itm/ or /p/
        return '/itm/' in url_lower or '/p/' in url_lower
    elif marketplace == 'mercari':
        # Mercari item links: /item/ followed by alphanumeric
        return '/item/' in url_lower and len(url.split('/item/')[-1]) > 5
    elif marketplace == 'facebook':
        # Facebook marketplace links: contains /marketplace/item/ or /marketplace/
        return '/marketplace/item/' in url_lower or ('/marketplace/' in url_lower and '?' in url_lower)
    elif marketplace == 'offerup':
        # OfferUp: typically /item/ or /web/item/
        return '/item/' in url_lower or '/web/item/' in url_lower
    return False

def scrape_marketplace(model, marketplace):
    """
    Search a marketplace for a used model and return (price, link, source) or (None, None, None).
    Improved version with BeautifulSoup fallback.
    """
    urls = {
        'ebay': f'https://www.ebay.com/sch/i.html?_nkw={quote_plus(model)}+used',
        'mercari': f'https://www.mercari.com/search/?keyword={quote_plus(model)}+used',
        'facebook': f'https://www.facebook.com/marketplace/search/?query={quote_plus(model)}+used',
        'offerup': f'https://offerup.com/search/?q={quote_plus(model)}+used'
    }
    url = urls.get(marketplace)
    if not url:
        return None, None, None

    try:
        # Use curl with a user-agent and timeout
        cmd = ['curl', '-s', '--max-time', '15', '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode != 0 or not result.stdout:
            return None, None, None

        html = result.stdout
        # First, try to extract price via regex (fast)
        price = extract_price_from_text(html)

        # Parse HTML with BeautifulSoup to find product links
        soup = BeautifulSoup(html, 'html.parser')
        # Find all anchor tags
        links = soup.find_all('a', href=True)
        product_link = None
        for link in links:
            href = link.get('href')
            # Make href absolute if needed
            if href.startswith('/'):
                if marketplace == 'ebay':
                    href = 'https://www.ebay.com' + href
                elif marketplace == 'mercari':
                    href = 'https://www.mercari.com' + href
                elif marketplace == 'facebook':
                    href = 'https://www.facebook.com' + href
                elif marketplace == 'offerup':
                    href = 'https://offerup.com' + href
            # Check if this looks like a product link
            if is_product_link(href, marketplace):
                product_link = href
                break  # take the first product-like link

        # If we didn't find a product link via heuristic, fallback to first href that looks like a product domain
        if not product_link and links:
            for link in links:
                href = link.get('href')
                if href and ('ebay.com' in href or 'mercari.com' in href or 'facebook.com' in href or 'offerup.com' in href):
                    # Make absolute
                    if href.startswith('/'):
                        if marketplace == 'ebay':
                            href = 'https://www.ebay.com' + href
                        elif marketplace == 'mercari':
                            href = 'https://www.mercari.com' + href
                        elif marketplace == 'facebook':
                            href = 'https://www.facebook.com' + href
                        elif marketplace == 'offerup':
                            href = 'https://offerup.com' + href
                    product_link = href
                    break

        # If we have a link but no price, try to extract price from the link's context or nearby text
        if product_link and price is None:
            # Search for price near the link in the original HTML (simplified)
            # We'll just use the regex on the whole HTML again; if still None, we can't proceed
            price = extract_price_from_text(html)

        # Validate price range
        if price is not None and (price < 2 or price > 1000):
            price = None

        if price is None or product_link is None:
            return None, None, None

        return price, product_link, marketplace

    except Exception as e:
        print(f"Error scraping {marketplace} for {model}: {e}")
        return None, None, None