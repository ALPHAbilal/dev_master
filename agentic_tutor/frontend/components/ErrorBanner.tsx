import { useTutor } from "@/lib/session";
import styles from "./ErrorBanner.module.css";
export default function ErrorBanner() {
  const tutor = useTutor();
  return tutor.error ? (
    <div className={styles.error} role="alert">
      {tutor.error}
      <button title="Dismiss" onClick={() => tutor.setError("")}>
        {" "}
        ×
      </button>
    </div>
  ) : null;
}
