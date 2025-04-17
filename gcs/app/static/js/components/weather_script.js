async function fetchWeather(lat, lon) {
    try {
        const apiKey = "a994d97b2a4037992168cf9bd8b9debf"; // OpenWeatherMap API key
        console.log("Fetching weather for coordinates:", lat, lon);

        const response = await fetch(
            `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&units=metric&appid=${apiKey}`
        );

        if (!response.ok) {
            console.error(`Weather API Error (${response.status}): ${await response.text()}`);
            throw new Error(`API Error ${response.status}: ${response.statusText}`);
        }

        const weatherData = await response.json();
        console.log("Weather data received:", weatherData);

        return {
            description: weatherData.weather[0].description,
            temperature: weatherData.main.temp * (9/5) + 32,
            humidity: weatherData.main.humidity,
            windSpeed: weatherData.wind.speed,
        };
    } catch (error) {
        console.error("Error fetching weather:", error);
        return null;
    }
}

async function displayWeather(lat, lon) {
    console.log("Displaying weather...");
    const weather = await fetchWeather(lat, lon);

    if (weather) {
        console.log("Weather data:", weather);

        document.getElementById("weather-description").textContent = weather.description;
        document.getElementById("weather-temperature").textContent = weather.temperature.toFixed(1) * (9/5) + 32;
        document.getElementById("weather-humidity").textContent = weather.humidity;
        document.getElementById("weather-wind").textContent = weather.windSpeed.toFixed(1);

        const weatherImage = document.getElementById("weather-image");
        const imageUrl = await fetchWeatherImage(weather.description);

        if (imageUrl) {
            weatherImage.src = imageUrl;
            weatherImage.style.display = "block";
        } else {
            weatherImage.style.display = "none"; // Hide image if not found
        }
    } else {
        document.getElementById("weather-description").textContent = "Weather data unavailable.";
    }
}

function fetchWeatherImage(description) {
    const weatherIconMap = {
        "clear sky": "https://openweathermap.org/img/wn/01d@2x.png",
        "few clouds": "https://openweathermap.org/img/wn/02d@2x.png",
        "scattered clouds": "https://openweathermap.org/img/wn/03d@2x.png",
        "broken clouds": "https://openweathermap.org/img/wn/04d@2x.png",
        "shower rain": "https://openweathermap.org/img/wn/09d@2x.png",
        "rain": "https://openweathermap.org/img/wn/10d@2x.png",
        "thunderstorm": "https://openweathermap.org/img/wn/11d@2x.png",
        "snow": "https://openweathermap.org/img/wn/13d@2x.png",
        "mist": "https://openweathermap.org/img/wn/50d@2x.png"
    };

    return weatherIconMap[description] || null;
}

export { displayWeather };