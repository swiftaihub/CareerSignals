export const HOME_ROUTES = {
  home: "/",
  howItWorks: "/#how-it-works",
  register: "/register",
  login: "/login",
  pricing: "/pricing",
  dashboard: "/dashboard"
} as const;

export const DEMO_PREVIEW_LABEL = "Illustrative preview · Demo workspace";

export const HERO_MATCHES = [
  {
    role: "Senior Analytics Engineer",
    company: "Fintech platform",
    score: 94,
    signals: ["Skill match", "Salary"]
  },
  {
    role: "Product Data Scientist",
    company: "AI workflow suite",
    score: 91,
    signals: ["Location", "Work model"]
  },
  {
    role: "Credit Risk Analyst",
    company: "Banking analytics",
    score: 86,
    signals: ["Visa signal", "Skills"]
  }
] as const;

export const NOISE_TO_SIGNAL_VALUES = [
  {
    title: "One focused workspace",
    body: "Bring relevant jobs, match signals, and application progress together."
  },
  {
    title: "Scores you can understand",
    body: "See the skills, preferences, and job details behind every recommendation."
  },
  {
    title: "Priorities that adapt to you",
    body: "Update your goals and let your ranking reflect what matters now."
  }
] as const;

export const HOW_IT_WORKS_STEPS = [
  {
    title: "Tell us what fits",
    body: "Add your target roles, skills, location, salary expectations, work arrangement, and other preferences."
  },
  {
    title: "We refresh the market",
    body: "CareerSignals continuously organizes job postings from supported sources into one consistent job universe."
  },
  {
    title: "Every role is evaluated",
    body: "Jobs are ranked using skills, seniority, salary, industry, location, work model, visa signals, and your personal priorities."
  },
  {
    title: "You move the best roles forward",
    body: "Review the strongest matches first, save opportunities, track applications, and keep momentum from application to interview."
  }
] as const;

export const PRODUCT_CAPABILITIES = [
  {
    title: "Top Matches",
    body: "Start every review with the roles showing the strongest evidence of fit."
  },
  {
    title: "Explainable Scores",
    body: "Understand how skills, preferences, salary, seniority, location, and other signals affect the ranking."
  },
  {
    title: "Skill Gap Insights",
    body: "See which capabilities repeatedly appear in the opportunities you care about."
  },
  {
    title: "Application Pipeline",
    body: "Move roles through saved, applied, interview, offer, rejected, and archived stages without spreadsheet drift."
  }
] as const;

export const TRUST_INDICATORS = [
  "Server-side credentials",
  "User-scoped results",
  "Protected personal settings",
  "Read-only demo environment"
] as const;
