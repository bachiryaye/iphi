import { useT } from "@/shared/i18n/context";
import { Link } from "react-router";

export function NotFoundPage() {
  const t = useT();
  return (
    <>
      <h1 className="text-display font-semibold">{t("Page not found")}</h1>
      <p className="text-text-muted">
        {t("This address does not match any IPHI view.")}{" "}
        <Link to="/" className="text-accent underline underline-offset-2">
          {t("Open the overview")}
        </Link>
        .
      </p>
    </>
  );
}
