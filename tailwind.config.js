/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/templates/**/*.html", "./static/js/**/*.js"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: "#00376E",
        secondary: "#007BC7",
        "background-light": "#FFFFFF",
        "background-dark": "#1F2937",
        "surface-light": "#F3F4F6",
        "surface-dark": "#374151",
        "text-light": "#000000",
        "text-dark": "#E5E7EB",
      },
      fontFamily: {
        display: ["Merriweather", "serif"],
        body: ["RO Sans", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0px",
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
