import type { JSX } from "react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { fetchProposal } from "./lib/api";
import type { Payload } from "./lib/types";
import { App } from "./App";
import { Loading } from "./states/Loading";
import { ErrorState } from "./states/ErrorState";
import "./theme.css";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const id = window.location.pathname.split("/").filter(Boolean).pop() ?? "";
const root = createRoot(document.getElementById("root")!);

function render(node: JSX.Element) {
  root.render(<StrictMode>{node}</StrictMode>);
}

if (!UUID.test(id)) {
  render(<ErrorState />);
} else {
  render(<Loading />);
  fetchProposal(id)
    .then((payload: Payload) => render(<App payload={payload} />))
    .catch(() => render(<ErrorState />));
}
