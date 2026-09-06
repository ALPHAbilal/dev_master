export default function Icon({
  name = "right",
  size = 15,
}: {
  name?: string;
  size?: number;
}) {
  const paths: Record<string, string> = {
    right: "M9 6l6 6-6 6",
    left: "M15 6l-6 6 6 6",
    plus: "M12 5v14M5 12h14",
    send: "M12 20V5M6 11l6-6 6 6",
    arrow: "M5 12h14M13 6l6 6-6 6",
    close: "M6 6l12 12M18 6L6 18",
    code: "M8 6l-5 6 5 6M16 6l5 6-5 6",
    test: "M9 3v6l-4.5 8.5A2 2 0 0 0 6 21h12a2 2 0 0 0 1.5-3.5L15 9V3M8 3h8",
    convo: "M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.5A8 8 0 1 1 21 12z",
    folder:
      "M3 7a2 2 0 0 1 2-2h3.5l2 2H19a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    file: "M13 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9zM13 3v6h6",
    settings:
      "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {name === "rail" ? (
        <>
          <rect x="3" y="4" width="18" height="16" rx="2.5" />
          <path d="M9 4v16" />
        </>
      ) : (
        <>
          <path d={paths[name] || paths.right} />
          {name === "settings" && <circle cx="12" cy="12" r="3" />}
        </>
      )}
    </svg>
  );
}
