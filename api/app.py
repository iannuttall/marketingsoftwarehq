import os
import time
import requests
import pandas as pd
from flask import Flask, render_template, abort, redirect, url_for, make_response
from flask_misaka import Misaka
from datetime import datetime
from flask_caching import Cache

app = Flask(__name__)
Misaka(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/')
def index():
    # Load the products data
    products = load_products()

    # Generate a list of tuples with the URL and the link text for the product review pages
    review_links = [(url_for('product_review', product_slug=row['slug']), row['name']) for _, row in products.iterrows()]

    # Generate a list of tuples with the URL and the link text for the comparison pages
    compare_links = [(url_for('compare_products', product_slug_1=row1['slug'], product_slug_2=row2['slug']),
                      f"{row1['name']} vs {row2['name']}")
                     for i, row1 in products.iterrows()
                     for _, row2 in products.iloc[i + 1:].iterrows()]

    # Pass the links to a template
    return render_template('index.html', review_links=review_links, compare_links=compare_links)

@app.route('/<product_slug>-review/')
def product_review(product_slug):
    products = load_products()

    product = products[products['slug'] == product_slug]

    if product.empty:
        abort(404)  # Product not found

    # Convert the product Series to a dictionary
    product_dict = product.iloc[0].to_dict()

    # Calculate the market average of the lowest price, excluding any products with a highest price of -1
    market_average = products[products['highest price'] != -1]['lowest price'].mean()

    # Get the lowest price of the current product
    product_price = product_dict['lowest price']

    # Calculate the percentage difference of the product's price from the market average
    percentage_difference = ((product_price - market_average) / market_average) * 100

    # Determine if the price is above or below average
    if percentage_difference > 0:
        price_status = "above the market average"
    elif percentage_difference < 0:
        price_status = "below the market average"
    else:
        price_status = "exactly at the market average"

    # Make the percentage difference absolute
    percentage_difference = abs(percentage_difference)

    # Get the count of unique services
    unique_services_count = products['slug'].nunique()

    # Add the calculated values to the product dictionary
    product_dict.update({
        'market_average': market_average,
        'percentage_difference': percentage_difference,
        'price_status': price_status,
        'unique_services_count': unique_services_count
    })

    # Generate a list of tuples with the URL and the link text for the comparison pages for the current product
    comparison_links = [(url_for('compare_products', product_slug_1=product_slug, product_slug_2=other_product_slug),
                         f"{product_dict['name']} vs {other_product_name}")
                        for other_product_slug, other_product_name in sorted(
                            [(row['slug'], row['name']) for _, row in products.iterrows() if row['slug'] != product_slug])]

    # Pass the product data and comparison links to a template
    return render_template('product_review.html', product=product_dict, comparison_links=comparison_links)



@app.route('/compare/<product_slug_1>-vs-<product_slug_2>/')
def compare_products(product_slug_1, product_slug_2):
    products = load_products()

    product1 = products[products['slug'] == product_slug_1]
    product2 = products[products['slug'] == product_slug_2]

    if product1.empty or product2.empty:
        abort(404)  # One or both products not found

    # Convert the product Series to dictionaries
    product1_dict = product1.iloc[0].to_dict()
    product2_dict = product2.iloc[0].to_dict()

    # Calculate the market average of the lowest price, excluding any products with a highest price of -1
    market_average = products[products['highest price'] != -1]['lowest price'].mean()

    # Get the lowest price of the current products
    product1_price = product1_dict['lowest price']
    product2_price = product2_dict['lowest price']

    # Calculate the percentage difference of the product's price from the market average
    percentage_difference_1 = ((product1_price - market_average) / market_average) * 100
    percentage_difference_2 = ((product2_price - market_average) / market_average) * 100

    # Determine if the price is above or below average
    if percentage_difference_1 > 0:
        price_status_1 = "above the market average"
    elif percentage_difference_1 < 0:
        price_status_1 = "below the market average"
    else:
        price_status_1 = "exactly at the market average"

    if percentage_difference_2 > 0:
        price_status_2 = "above the market average"
    elif percentage_difference_2 < 0:
        price_status_2 = "below the market average"
    else:
        price_status_2 = "exactly at the market average"

    # Make the percentage difference absolute
    percentage_difference_1 = abs(percentage_difference_1)
    percentage_difference_2 = abs(percentage_difference_2)

    # Get the count of unique services
    unique_services_count = products['slug'].nunique()

    # Add the calculated values to the product dictionaries
    product1_dict.update({
        'market_average': market_average,
        'percentage_difference': percentage_difference_1,
        'price_status': price_status_1,
        'unique_services_count': unique_services_count
    })
    product2_dict.update({
        'market_average': market_average,
        'percentage_difference': percentage_difference_2,
        'price_status': price_status_2,
        'unique_services_count': unique_services_count
    })

    # Pass the product data to a template
    return render_template('compare_products.html', product1=product1_dict, product2=product2_dict)


def download_sheet():
    google_sheet_id = "1A4ClDMHtqZNG_IJmMvS4cJA7eHl1JTiK5vXPodvVaHc"
    sheet_url = f"https://docs.google.com/spreadsheets/d/{google_sheet_id}/export?format=csv"

    response = requests.get(sheet_url)
    assert response.status_code == 200, 'Wrong status code'
    
    with open('products.csv', 'wb') as f:
        f.write(response.content)

@cache.cached(timeout=60*60*24)
def load_products():
    # Google Sheets CSV URL
    google_sheet_id = "1A4ClDMHtqZNG_IJmMvS4cJA7eHl1JTiK5vXPodvVaHc"
    sheet_url = f"https://docs.google.com/spreadsheets/d/{google_sheet_id}/export?format=csv"

    # Load the products data, treating empty strings as NaN
    products = pd.read_csv(sheet_url, na_values=[''])

    # Fill NaN values with False
    products = products.fillna(False)

    return products

@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    """Generate sitemap.xml. Makes a list of urls and date modified."""
    pages = []

    # static pages
    for rule in app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments) == 0 and rule.rule != '/sitemap.xml':
            pages.append(
                [url_for(rule.endpoint, _external=True), datetime.now().strftime('%Y-%m-%d')]
            )

    # product review pages
    products = load_products()
    for _, row in products.iterrows():
        url = url_for('product_review', product_slug=row['slug'], _external=True)
        modified_time = datetime.now().strftime('%Y-%m-%d')  # Assuming the page was last modified now
        pages.append([url, modified_time])

    # product comparison pages
    for i, row1 in products.iterrows():
        for _, row2 in products.iloc[i + 1:].iterrows():
            url = url_for('compare_products', product_slug_1=row1['slug'], product_slug_2=row2['slug'], _external=True)
            modified_time = datetime.now().strftime('%Y-%m-%d')  # Assuming the page was last modified now
            pages.append([url, modified_time])

    sitemap_xml = render_template('sitemap_template.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"    
    
    return response



if __name__ == '__main__':
    app.run(debug=True)