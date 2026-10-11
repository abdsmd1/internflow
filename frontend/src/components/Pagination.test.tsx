import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Pagination } from "./Pagination";

describe("pagination", () => {
  it("disparaît quand tout tient sur une page", () => {
    const { container } = render(<Pagination offset={0} limit={20} total={5} onChange={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("navigue de page en page", async () => {
    const onChange = vi.fn();
    render(<Pagination offset={20} limit={20} total={45} onChange={onChange} />);
    expect(screen.getByText("21–40 sur 45")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Suivant" }));
    await userEvent.click(screen.getByRole("button", { name: "Précédent" }));
    expect(onChange.mock.calls).toEqual([[40], [0]]);
  });

  it("bloque les boutons aux extrémités", () => {
    render(<Pagination offset={40} limit={20} total={45} onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Suivant" })).toBeDisabled();
  });
});
