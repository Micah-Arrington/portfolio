from flask import Flask, request, jsonify
import subprocess, requests
import googlemaps
from googlemaps.exceptions import ApiError, TransportError

app = Flask(__name__)


@app.route('/nearest_hospital', methods=['POST', 'GET'])
def find_nearest_hospital():
    """
    Expects JSON body:
    {
        "address": "London, UK",
        "api_key": "****api-key****"
    }
    """

    data = request.get_json()
    if not data or 'address' not in data or 'api_key' not in data:
        return jsonify({'error': 'JSON body must include an "address" and "api_key" field'}), 400

    api_key = data['api_key']
    address = data['address']

    gmaps = googlemaps.Client(key=api_key)

    try:
        resp = gmaps.geocode(address)
    except (ApiError, TransportError) as e:
        return jsonify({'error': f"Error calling Geocoding API: {e}"}), 500

    if isinstance(resp, dict):
        results = resp.get('results', [])
    else:
        results = resp

    if not results:
        return jsonify({'error': f"No geocoding results for '{address}'."}), 404

    loc = results[0]['geometry']['location']
    latlng = (loc['lat'], loc['lng'])

    try:
        places_resp = gmaps.places_nearby(
            location=latlng,
            rank_by='distance',
            type='hospital'
        )
    except (ApiError, TransportError) as e:
        return jsonify({'error': f"Error calling Places API: {e}"}), 500

    if isinstance(places_resp, dict):
        hospitals = places_resp.get('results', [])
    else:
        hospitals = places_resp.get('results', [])

    if not hospitals:
        return jsonify({'error': "No hospitals found nearby."}), 404

    # Define keywords for "big" hospitals
    big_keywords = [
        "medical center", "university hospital", "general hospital",
        "regional hospital", "trauma center", "children's hospital"
    ]

    def is_big(hospital):
        name = hospital.get('name', '').lower()
        return any(keyword in name for keyword in big_keywords)

    big_hospitals = [h for h in hospitals if is_big(h)]

    if len(big_hospitals) < 5:
        remaining = [h for h in hospitals if h not in big_hospitals]
        big_hospitals.extend(remaining[:5 - len(big_hospitals)])

    # Only return up to 5, sorted by proximity
    top_hospitals = []
    for hospital in big_hospitals[:5]:
        hospital_name = hospital.get('name', 'UNKNOWN')
        hospital_address = hospital.get('vicinity', hospital.get('formatted_address', ''))
        hospital_rating = hospital.get('rating', None)
        hospital_ratings_total = hospital.get('user_ratings_total', None)
        hospital_place_id = hospital.get('place_id', None)

        url = f"https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": hospital_place_id,
            "fields": "formatted_phone_number",
            "key": api_key
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if "result" in data and "formatted_phone_number" in data["result"]:
                hospital_phone_number = data["result"]["formatted_phone_number"]
            else:
                hospital_phone_number =  "Phone number not available for this place."
        else:
            hospital_phone_number =  "Phone number not available for this place."

        top_hospitals.append({
            'name': hospital_name,
            'address': hospital_address,
            'phone_number': hospital_phone_number,
            'rating': hospital_rating,
            'user_ratings_total': hospital_ratings_total
        })

    return jsonify({
        'biggest_hospitals_near': address,
        'hospitals': top_hospitals
    })

@app.route('/nearest_embassy', methods=['POST', 'GET'])
def find_nearest_embassy():
    """
    Expects JSON body:
    {
        "address": "London, UK",
        "api_key": "****api-key****"
    }
    """
    data = request.get_json()
    if not data or 'address' not in data or 'api_key' not in data:
        return jsonify({'error': 'JSON body must include an "address" and "api_key" field'}), 400

    api_key = data['api_key']
    address = data['address']

    gmaps = googlemaps.Client(key=api_key)

    try:
        resp = gmaps.geocode(address)
    except (ApiError, TransportError) as e:
        return jsonify({'error': f"Error calling Geocoding API: {e}"}), 500

    # Normalize: if we got a dict, pull out 'results'; otherwise assume it's already a list
    if isinstance(resp, dict):
        results = resp.get('results', [])
    else:
        results = resp

    if not results:
        return jsonify({'error': f"No geocoding results for '{address}'."}), 404

    # Safe now to index into results[0]
    loc = results[0]['geometry']['location']
    latlng = (loc['lat'], loc['lng'])

    try:
        # Search for US embassies nearby
        places_resp = gmaps.places_nearby(
            location=latlng,
            rank_by='distance',
            keyword='US Embassy',
            type='embassy'
        )
    except (ApiError, TransportError) as e:
        return jsonify({'error': f"Error calling Places API: {e}"}), 500

    # Normalize in case it's a dict
    if isinstance(places_resp, dict):
        embassies = places_resp.get('results', [])
    else:
        embassies = places_resp.get('results', [])

    if not embassies:
        return jsonify({'error': "No US embassies found nearby."}), 404

    nearest = embassies[0]
    embassy_name = nearest.get('name', 'UNKNOWN')
    embassy_address = nearest.get('vicinity', nearest.get('formatted_address', ''))
    embassy_place_id = nearest.get('place_id', None)

    url = f"https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": embassy_place_id,
        "fields": "formatted_phone_number",
        "key": api_key
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if "result" in data and "formatted_phone_number" in data["result"]:
            embassy_phone_number = data["result"]["formatted_phone_number"]
        else:
            embassy_phone_number =  "Phone number not available for this place."
    else:
        embassy_phone_number =  "Phone number not available for this place."

    return jsonify({
        'nearest_embassy_to': address,
        'name': embassy_name,
        'address': embassy_address,
        'embassy_phone': embassy_phone_number
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    