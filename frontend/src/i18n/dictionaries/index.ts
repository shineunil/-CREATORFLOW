import type { Locale } from "../config";
import { en, type Dictionary } from "./en";
import { ko } from "./ko";

export type { Dictionary, Rich } from "./en";

export const dictionaries: Record<Locale, Dictionary> = { en, ko };
