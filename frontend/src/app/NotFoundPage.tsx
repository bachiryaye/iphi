import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <>
      <h1 className="text-display font-semibold">Page not found</h1>
      <p className="text-text-muted">
        This address does not match any IPHI view.{" "}
        <Link to="/" className="text-accent underline underline-offset-2">
          Open the overview
        </Link>
        .
      </p>
    </>
  );
}
