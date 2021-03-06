from datetime import datetime

import requests
from django.core.cache import cache
from rest_framework.response import Response


def get_weather():
    WEATHER_PREDICTION_VALIDITY = 10800  # 3 hours
    WEATHER_TYPES_VALIDITY = 3600 * 24 * 7  # 1 week

    weather_types = cache.get("weather_types")
    if weather_types is None:
        response = requests.get("http://api.ipma.pt/open-data/weather-type-classe.json")
        if response.status_code != 200:
            return Response({'error': 'Provider is down'})

        weather_types = dict()
        for entry in response.json()['data']:
            weather_types[entry['idWeatherType']] = entry['descIdWeatherTypePT']
        cache.set("weather_types", weather_types, timeout=WEATHER_TYPES_VALIDITY)

    prediction = cache.get("weather_prediction")
    prediction = None
    if prediction is None:
        response = requests.get("http://api.ipma.pt/public-data/forecast/aggregate/1150300.json")
        if response.status_code != 200:
            return {'error': 'Provider is down'}

        hours = []
        days = []
        prevision_date = None
        for entry in response.json():
            min_temp, med_temp, max_temp, rain_prob, weather_type = None, None, None, None, None
            for_range, humidity, wind_direction, wind_strength = None, None, None, None
            if 'tMin' in entry:
                min_temp = float(entry['tMin'])
            if 'tMax' in entry:
                max_temp = float(entry['tMax'])
            if 'tMed' in entry:
                med_temp = float(entry['tMed'])
            if 'probabilidadePrecipita' in entry:
                rain_prob = float(entry['probabilidadePrecipita'])
            if 'idTipoTempo' in entry:
                weather_type = weather_types[entry['idTipoTempo']]
            if 'ffVento' in entry:
                wind_strength = float(entry['ffVento'])
            if 'ddVento' in entry:
                wind_direction = entry['ddVento']
            if 'hR' in entry:
                humidity = float(entry['hR'])
            if prevision_date is None:
                prevision_date = datetime.strptime(entry['dataUpdate'], '%Y-%m-%dT%H:%M:%S')
            date = datetime.strptime(entry['dataPrev'], '%Y-%m-%dT%H:%M:%S')

            if 'intervaloHora' in entry:
                for_range = entry['intervaloHora']
            if min_temp is None:
                if date.today().date() == date.date():
                    hours.append({
                        'temperature': med_temp,
                        'rain': rain_prob,
                        'hour': date.hour,
                        'humidity': humidity,
                        'wind_direction': wind_direction,
                        'wind_strength': wind_strength,
                        'type': weather_type})
            else:
                days.append({
                    'min': min_temp,
                    'max': max_temp,
                    'rain': rain_prob,
                    'date': date,
                    'range': for_range,
                    'wind_direction': wind_direction,
                    'type': weather_type})
        hours.sort(key=lambda x: x['hour'])
        days.sort(key=lambda x: x['date'])
        prediction = {
            'hours': hours,
            'days': days}
        cache.set("weather_prediction", prediction, timeout=WEATHER_PREDICTION_VALIDITY)

    return prediction
