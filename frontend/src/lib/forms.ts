/** Lit les champs texte d'un formulaire (un champ absent vaut une chaîne vide). */
export function readForm(form: HTMLFormElement): (name: string) => string {
  const data = new FormData(form);
  return (name) => {
    const value = data.get(name);
    return typeof value === "string" ? value : "";
  };
}
