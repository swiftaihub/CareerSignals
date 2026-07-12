import { Layers3, Sparkles, X } from "lucide-react";

import { SearchableMultiSelect } from "@/components/settings/searchable-multi-select";
import { SectionCard } from "@/components/shared/section-card";
import type { PreferenceOption, PreferenceSkill } from "@/lib/types";

export function SkillsEditor({
  skills,
  categories,
  disabled,
  onSkillsChange,
  onCategoriesChange
}: {
  skills: PreferenceSkill[];
  categories: string[];
  disabled: boolean;
  onSkillsChange: (skills: PreferenceSkill[]) => void;
  onCategoriesChange: (categories: string[]) => void;
}) {
  const skillValues = skills.map((skill) => skill.name);
  const categoryOptions: PreferenceOption[] = categories.map((category) => ({ value: category, label: category }));

  function updateSkillNames(names: string[]) {
    onSkillsChange(names.map((name) => skills.find((skill) => skill.name.toLocaleLowerCase() === name.toLocaleLowerCase()) || { name, category: null }));
  }

  function updateCategories(next: string[]) {
    const allowed = new Set(next.map((category) => category.toLocaleLowerCase()));
    onCategoriesChange(next);
    onSkillsChange(skills.map((skill) => ({
      ...skill,
      category: skill.category && allowed.has(skill.category.toLocaleLowerCase()) ? skill.category : null
    })));
  }

  return (
    <SectionCard
      className="mt-6 scroll-mt-24"
      title="Skills & Experience"
      description="Add skills, tools, domains, certifications, or areas of expertise from any profession. Alias generation happens automatically."
    >
      <div className="space-y-6" id="skills-experience">
        <SearchableMultiSelect
          allowCustom
          disabled={disabled}
          id="unified-skills"
          label="Your skills and expertise"
          description="Examples include Salesforce, Registered Nursing, CNC Programming, Contract Negotiation, Python, or Healthcare Operations."
          options={skillValues.map((name) => ({ value: name, label: name }))}
          placeholder="Add a skill, tool, domain, certification, or area of expertise"
          values={skillValues}
          onChange={updateSkillNames}
        />

        <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <SearchableMultiSelect
              allowCustom
              disabled={disabled}
              id="skill-categories"
              label="Optional custom categories"
              description="Organize skills in categories meaningful to your work. Uncategorized skills remain fully supported."
              options={categoryOptions}
              placeholder="Add a category"
              values={categories}
              onChange={updateCategories}
            />
            <div className="mt-4 rounded-xl border border-teal-100 bg-teal-50/70 p-4 text-sm text-teal-950">
              <div className="flex items-center gap-2 font-semibold"><Sparkles className="h-4 w-4" />Aliases generated for you</div>
              <p className="mt-2 leading-6">CareerSignals normalizes safe variants and reuses its shared alias catalog before your personal pipeline starts.</p>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-background/70 p-4">
            <div className="flex items-center gap-2"><Layers3 className="h-4 w-4 text-primary" /><h3 className="text-sm font-semibold">Skill organization</h3></div>
            <div className="mt-3 space-y-2">
              {skills.length ? skills.map((skill, index) => (
                <div className="grid gap-2 rounded-lg border border-border bg-card p-3 sm:grid-cols-[1fr_220px_auto] sm:items-center" key={skill.name}>
                  <span className="truncate text-sm font-medium">{skill.name}</span>
                  <label className="sr-only" htmlFor={`skill-category-${index}`}>Category for {skill.name}</label>
                  <select
                    className="select"
                    disabled={disabled}
                    id={`skill-category-${index}`}
                    value={skill.category || ""}
                    onChange={(event) => onSkillsChange(skills.map((item) => item.name === skill.name ? { ...item, category: event.target.value || null } : item))}
                  >
                    <option value="">General / uncategorized</option>
                    {categories.map((category) => <option key={category} value={category}>{category}</option>)}
                  </select>
                  <button aria-label={`Remove ${skill.name}`} className="btn h-10 w-10 px-0" disabled={disabled} type="button" onClick={() => onSkillsChange(skills.filter((item) => item.name !== skill.name))}><X className="h-4 w-4" /></button>
                </div>
              )) : <p className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">Add skills above. Categories are optional.</p>}
            </div>
          </div>
        </div>
      </div>
    </SectionCard>
  );
}
