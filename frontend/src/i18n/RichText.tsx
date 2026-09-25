import type { Rich } from "./dictionaries";

export default function RichText({ value, strongClassName }: { value: Rich; strongClassName: string }) {
  return (
    <>
      {value.before}
      <span className={strongClassName}>{value.strong}</span>
      {value.after}
    </>
  );
}
