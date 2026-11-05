// One Piece Character Explorer — behaviour lives here.
//
// How it works, step by step:
//   step 3: characters.json already holds the merged data (loaded below)
//   step 4: render one card per character  <-- this step
//   step 5: search by name
//   step 6: crew + status filters
//   step 7: detail view on click

// All characters, loaded once from characters.json.
let characters = [];

// Load the data, then draw the cards. Runs when the page finishes loading.
async function loadCharacters() {
  try {
    const response = await fetch("characters.json");
    characters = await response.json();
    render(characters);
  } catch (error) {
    // If the file cannot be loaded (e.g. page opened without a server),
    // say so instead of leaving a blank page.
    document.getElementById("results").innerHTML =
      "<p>Could not load characters.json. Open this page through a local server or GitHub Pages.</p>";
  }
}

// Build one card element for a character. Missing fields are left out:
// not every character has an image, a bounty, or a crew.
function cardFor(character) {
  const card = document.createElement("article");
  card.className = "card";

  // Portrait when we have one; otherwise a block with the first letter.
  if (character.image) {
    const img = document.createElement("img");
    // The wiki answers 404 when the request arrives with a github.io
    // referer, so ask the browser not to send one for these images.
    // Set before src so the policy applies to the first request.
    img.referrerPolicy = "no-referrer";
    img.src = character.image;
    img.alt = character.name;
    img.loading = "lazy"; // only load images as they scroll into view
    // The wiki generates thumbnails on demand, so the first request for a
    // portrait can answer 404 while the file is being made. Retry once
    // after a pause; only if that also fails, swap in the letter block.
    let tries = 0;
    img.addEventListener("error", () => {
      tries += 1;
      if (tries === 1) {
        setTimeout(() => { img.src = character.image; }, 1000);
      } else {
        const noImage = document.createElement("div");
        noImage.className = "no-image";
        noImage.textContent = character.name.charAt(0);
        img.replaceWith(noImage);
      }
    });
    card.appendChild(img);
  } else {
    const noImage = document.createElement("div");
    noImage.className = "no-image";
    noImage.textContent = character.name.charAt(0);
    card.appendChild(noImage);
  }

  const name = document.createElement("h2");
  name.textContent = character.name;
  card.appendChild(name);

  const status = document.createElement("p");
  status.className = "status " + character.status;
  status.textContent = character.status === "alive" ? "Alive"
    : character.status === "deceased" ? "Deceased" : "Unknown";
  card.appendChild(status);

  if (character.bounty) {
    const bounty = document.createElement("p");
    bounty.textContent = "Bounty: " + character.bounty + " Berry";
    card.appendChild(bounty);
  }

  if (character.crew) {
    const crew = document.createElement("p");
    crew.textContent = "Crew: " + character.crew;
    card.appendChild(crew);
  }

  return card;
}

// Draw the given list of characters into the results grid.
function render(list) {
  const results = document.getElementById("results");
  results.innerHTML = "";

  const count = document.createElement("p");
  count.className = "count";
  count.textContent = "Showing " + list.length + " characters";
  results.appendChild(count);

  for (const character of list) {
    results.appendChild(cardFor(character));
  }
}

loadCharacters();
