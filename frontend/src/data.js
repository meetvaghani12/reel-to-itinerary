export const STEPS = [
  { key: "landing", n: "01", label: "Link" },
  { key: "extracting", n: "02", label: "Extract" },
  { key: "places", n: "03", label: "Places" },
  { key: "persona", n: "04", label: "Persona" },
  { key: "plans", n: "05", label: "Plans" },
  { key: "itinerary", n: "06", label: "Itinerary" },
];

export const PIPELINE = [
  { icon: "download", title: "Fetch", body: "Transcript, description, metadata & visible location tags from the video." },
  { icon: "auto_awesome", title: "Extract", body: "LLM identifies specific places, activities and the underlying travel vibe." },
  { icon: "travel_explore", title: "Resolve", body: "Each place validated against Google Places for coordinates & price tier." },
  { icon: "route", title: "Generate", body: "Three persona-tuned itineraries with real end-to-end cost estimates." },
];

export const QUESTIONS = [
  { key: "style", title: "What kind of trip?", sub: "Sets the tone for how we sequence your days.", options: [
    { val: "culture", label: "Culture & history", hint: "Souks, old town, museums", icon: "account_balance" },
    { val: "adventure", label: "Adventure & outdoors", hint: "Hikes, water, activities", icon: "terrain" },
    { val: "relax", label: "Luxury & relaxation", hint: "Beaches, spas, fine dining", icon: "spa" },
    { val: "social", label: "Nightlife & social", hint: "Bars, rooftops, dining", icon: "nightlife" },
  ] },
  { key: "budget", title: "What's your budget?", sub: "Roughly, per person, all-in for the trip.", options: [
    { val: "low", label: "Lean", hint: "Hostels & street food", icon: "savings" },
    { val: "mid", label: "Comfortable", hint: "3–4★ & nice meals", icon: "account_balance_wallet" },
    { val: "high", label: "No compromises", hint: "5★ & premium", icon: "diamond" },
    { val: "flex", label: "I'm flexible", hint: "Show me the range", icon: "tune" },
  ] },
  { key: "group", title: "Who is travelling?", sub: "We size accommodation and tours accordingly.", options: [
    { val: "solo", label: "Solo", hint: "Just me", icon: "person" },
    { val: "couple", label: "Couple", hint: "Two of us", icon: "favorite" },
    { val: "friends", label: "Friends", hint: "A small group", icon: "group" },
    { val: "family", label: "Family", hint: "With kids", icon: "family_restroom" },
  ] },
  { key: "pace", title: "How fast do you move?", sub: "Controls how many stops we pack per day.", options: [
    { val: "slow", label: "Slow & immersive", hint: "2–3 stops a day", icon: "self_improvement" },
    { val: "balanced", label: "Balanced", hint: "A steady rhythm", icon: "balance" },
    { val: "packed", label: "Packed & fast", hint: "See everything", icon: "bolt" },
    { val: "surprise", label: "Surprise me", hint: "You decide", icon: "casino" },
  ] },
];

export const PLAN_META = {
  budget_backpacker: { kicker: "Budget", name: "Budget Backpacker", icon: "backpack", accent: "#CE8A5C" },
  comfort_traveller: { kicker: "Comfort", name: "Comfort Traveller", icon: "king_bed", accent: "#C4623D" },
  luxury_escape: { kicker: "Luxury", name: "Luxury Escape", icon: "diamond", accent: "#8A3D22" },
};
export const PLAN_ORDER = ["budget_backpacker", "comfort_traveller", "luxury_escape"];

export const TYPE_ICON = {
  restaurant: "restaurant", cafe: "local_cafe", hotel: "bed", landmark: "account_balance",
  neighborhood: "location_city", activity: "local_activity", viewpoint: "visibility",
  market: "storefront", beach: "beach_access", temple: "temple_buddhist", museum: "museum",
  bar: "nightlife", other: "place",
};

export const COST_META = {
  flights: { label: "Flights (indicative)", icon: "flight" },
  accommodation: { label: "Accommodation", icon: "bed" },
  activities: { label: "Activities & tours", icon: "confirmation_number" },
  food: { label: "Food", icon: "restaurant" },
  transport: { label: "Local transport", icon: "directions_car" },
};
export const COST_KEYS = ["flights", "accommodation", "activities", "food", "transport"];

export const cap = (x) => (x ? x.charAt(0).toUpperCase() + x.slice(1) : x);
export const typeIcon = (t) => TYPE_ICON[(t || "other").toLowerCase()] || "place";

// Costs come from the backend in USD.
export const fmt = (n) => "$" + Math.round(Number(n) || 0).toLocaleString("en-US");
