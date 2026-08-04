// GitHub Pages needs the deployed API; self-hosted serves from same origin
const API_BASE_URL = window.location.hostname === 'joaofmsilva1979.github.io'
  ? 'https://api.notara.app'
  : '';
