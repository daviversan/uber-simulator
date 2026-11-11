// Tela de entrada: o usuário informa onde o motorista começa e entra no mapa.

// Validação no CLIENTE é conveniência (feedback imediato, sem ida e volta). Não é
// segurança: quem manda a regra é o servidor (o `JoinMessage` valida de novo os
// mesmos limites). Os dois lados checam porque confiam em coisas diferentes: este
// confia no usuário para ajudá-lo, o servidor não confia em ninguém.
export function parseCoordinate(raw, limit, label) {
  // Quem digita em pt-BR escreve "-23,55": troca a vírgula pelo ponto.
  const text = String(raw).trim().replace(",", ".");
  if (text === "") return { error: `${label} é obrigatória` };
  const value = Number(text);
  if (!Number.isFinite(value)) return { error: `${label} deve ser um número` };
  if (Math.abs(value) > limit) return { error: `${label} deve estar entre -${limit} e ${limit}` };
  return { value };
}

export function parseLocation(latRaw, lonRaw) {
  const lat = parseCoordinate(latRaw, 90, "Latitude");
  if (lat.error) return { error: lat.error };
  const lon = parseCoordinate(lonRaw, 180, "Longitude");
  if (lon.error) return { error: lon.error };
  return { pos: { lat: lat.value, lon: lon.value } };
}

// `loadCities` e `onSubmit` entram por parâmetro: esta tela não sabe se as
// cidades vêm do servidor ou de uma lista fixa, nem o que acontece depois
// de entrar. Só cuida do formulário.
export function setupJoinScreen({ driverId, initial, loadCities, onSubmit }) {
  const form = document.getElementById("join-form");
  const latInput = document.getElementById("join-lat");
  const lonInput = document.getElementById("join-lon");
  const citySelect = document.getElementById("join-city");
  const errorEl = document.getElementById("join-error");
  const submitBtn = form.querySelector("button[type=submit]");

  document.getElementById("join-driver-id").textContent = driverId;
  if (initial) {
    latInput.value = initial.lat;
    lonInput.value = initial.lon;
  }

  const showError = (message) => {
    errorEl.textContent = message;
    errorEl.hidden = !message;
  };

  loadCities()
    .then((cities) => {
      for (const city of cities) {
        const option = new Option(city.name, city.city_id);
        option.dataset.lat = city.center.lat;
        option.dataset.lon = city.center.lon;
        citySelect.add(option);
      }
    })
    .catch(() => showError("não consegui carregar a lista de cidades — digite as coordenadas"));

  citySelect.addEventListener("change", () => {
    const option = citySelect.selectedOptions[0];
    if (!option?.dataset.lat) return;
    latInput.value = option.dataset.lat;
    lonInput.value = option.dataset.lon;
    showError("");
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const { pos, error } = parseLocation(latInput.value, lonInput.value);
    if (error) return showError(error);
    showError("");
    submitBtn.disabled = true; // evita duplo clique mandando dois joins
    try {
      await onSubmit(pos);
    } catch (err) {
      showError(err.message);
      submitBtn.disabled = false; // permite corrigir e tentar de novo
    }
  });
}
