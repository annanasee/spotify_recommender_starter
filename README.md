# System rekomendacji muzycznych oparty o Spotify API

Projekt inżynierski realizowany w ramach studiów na kierunku Informatyka.  
Celem projektu jest stworzenie systemu rekomendacji muzyki z wykorzystaniem danych użytkownika oraz uczenia maszynowego.  
Dane pobierane są z **Spotify Web API** z użyciem biblioteki **Spotipy**.  

---

## Funkcjonalności
- Pobieranie danych o zapisanych utworach użytkownika  
- Zbieranie cech audio utworów (tempo, energia, taneczność itp.)  
- Pobieranie informacji o wykonawcach  
- Budowa katalogu muzycznego w formacie CSV  
- (planowane) moduł rekomendacyjny porównujący dwa podejścia:  
  - rekomendacje na podstawie historii odtwarzania  
  - rekomendacje na podstawie zadeklarowanych preferencji użytkownika  

---

## Wymagania
- Python 3.10+  
- Konto deweloperskie Spotify i zarejestrowana aplikacja  
- Biblioteki: (instalowane z `requirements.txt`)  
  - spotipy  
  - pandas  
  - numpy  
  - scikit-learn  

---

## Instalacja i konfiguracja

1. Sklonuj repozytorium:  
   ```bash
   git clone https://github.com/annanasee/spotify_recommender_starter.git
   cd spotify_recommender_starter
   ```

2. Utwórz i aktywuj wirtualne środowisko:  
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/Mac
   .venv\Scripts\activate      # Windows
   ```

3. Zainstaluj wymagane biblioteki:  
   ```bash
   pip install -r requirements.txt
   ```

4. Skonfiguruj plik `.env` w katalogu głównym (na podstawie `.env.example`):  
   ```
   SPOTIPY_CLIENT_ID=twoje_client_id
   SPOTIPY_CLIENT_SECRET=twoje_client_secret
   SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
   ```

---

## Struktura katalogów
```
spotify_recommender_starter/
│
├── data/
│   ├── raw/             # dane surowe z API (tracks.csv, audio_features.csv, artists.csv)
│   └── out/             # dane przetworzone (np. catalog.csv)
│
├── src/
│   ├── fetch_api.py      # pobieranie danych z Spotify
│   └── build_catalog.py  # budowa katalogu muzycznego
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## Uruchomienie projektu

1. Pobierz dane z API:  
   ```bash
   python src/fetch_api.py
   ```

   Dane zostaną zapisane w katalogu `data/raw/`.

2. Zbuduj katalog muzyczny:  
   ```bash
   python src/build_catalog.py
   ```

   Wynikowy plik (np. `catalog.csv`) pojawi się w katalogu `data/out/`.

---

## Przykładowy wynik

Fragment pliku `catalog.csv`:  

| track_id      | name       | artist       | danceability | energy | tempo |
|---------------|------------|--------------|--------------|--------|-------|
| 3n3Ppam7vgaVa1iaRUc9Lp | Something | The Beatles | 0.67 | 0.55 | 120.5 |
| ...           | ...        | ...          | ...          | ...    | ...   |

---

## Dalszy rozwój
- Implementacja algorytmów rekomendacyjnych (filtracja kolaboratywna, modele oparte na cechach audio)  
- Ewaluacja jakości rekomendacji (precision, recall itp.)  
- Wizualizacje danych muzycznych  
- Interfejs użytkownika (np. aplikacja webowa)  

---

## Autor
Anna Szymańska  

---

## Licencja
Projekt udostępniony na licencji MIT.  
