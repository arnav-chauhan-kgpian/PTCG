import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Bot,
  Brain,
  Gamepad2,
  Hammer,
  Home,
  LayoutDashboard,
  Library,
  Microscope,
  Settings,
  Sparkles,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  description?: string;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    label: "Workspace",
    items: [
      { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard, description: "Overview & metrics" },
      { title: "Battle Arena", href: "/battle", icon: Gamepad2, badge: "Live", description: "Watch the agent play" },
      { title: "Game Analysis", href: "/analysis", icon: Microscope, description: "Explain MCTS decisions" },
    ],
  },
  {
    label: "Decks",
    items: [
      { title: "Deck Builder", href: "/deck-builder", icon: Hammer, description: "Build with the AI" },
      { title: "Deck Analyzer", href: "/deck-analyzer", icon: Brain, description: "Score any decklist" },
      { title: "Card Database", href: "/cards", icon: Library, description: "1,267 cards" },
    ],
  },
  {
    label: "Engine",
    items: [
      { title: "Training", href: "/training", icon: Activity, description: "Self-play telemetry" },
      { title: "Benchmarks", href: "/benchmarks", icon: BarChart3, description: "Performance profiles" },
    ],
  },
  {
    label: "Account",
    items: [
      { title: "Settings", href: "/settings", icon: Settings },
      { title: "About", href: "/about", icon: Sparkles },
    ],
  },
];

export const topLevelNav: NavItem[] = [
  { title: "Home", href: "/", icon: Home },
  { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { title: "Battle", href: "/battle", icon: Bot },
];
