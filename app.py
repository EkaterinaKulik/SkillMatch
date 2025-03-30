import streamlit as st
from analysis import (
    get_links,
    vacancy_description_and_applicant_skills,
    plotly_kde_distribution
)
app_title = 'SkillMatch'
st.set_page_config(page_title=app_title)
st.title('SkillMatch: Match Your Skills to the Right Job')
st.markdown("""
Choose a job title and your current skill level from the menu on the left.  We'll check your skill match and provide personalized recommendations.
""")
st.sidebar.markdown("## Select Job and Skill Level")
position = st.sidebar.text_input("**Enter your job title**", placeholder="e.g. Data Analyst, Frontend Developer")
grade_option = st.sidebar.selectbox(
    "**Select your experience level**",
    ("Intern", "Junior", "Middle", "Senior", "Lead", "Principal"),
    index=None,
    placeholder="Choose a level from the list"
)
if "skills" not in st.session_state:
    st.session_state["skills"] = []

def add_skill():
    skill = st.session_state.skill_input.strip()
    if skill and skill not in st.session_state["skills"]:
        st.session_state["skills"].append(skill)
        st.session_state.skill_input = ""
st.sidebar.text_input(
    "**Enter your skills:**",
    placeholder="e.g. Python, SQL, React",
    key="skill_input",
    on_change=add_skill
)

st.sidebar.write("Selected skills:")
for skill in st.session_state["skills"]:
    st.sidebar.badge(skill)

if st.sidebar.button("Clear all skills"):
    st.session_state["skills"].clear()

_, _, right = st.sidebar.columns(3)
if right.button("Send", type="primary"):
  links = get_links(position, grade_option, pages=1)
  result = vacancy_description_and_applicant_skills(position, st.session_state["skills"], links)

  if "questions" in result and "offers" in result:
    st.subheader("You're ready for the interview!")
    st.metric(label="Similarity score", value=f"{result['similarity_score']:.2f}")
    fig = plotly_kde_distribution(result['precision_list'], position)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Suggested Interview Questions:")
    for q in result["questions"]:
        st.markdown(f"- {q}")

    st.markdown("### Top Matching Vacancies:")
    for vacancy in result["offers"]: 
        st.markdown(f"[{vacancy['name']}]({vacancy['alternate_url']})")
        st.markdown(f"{vacancy['description']}")
        st.markdown("---")

  else:
    st.subheader("You might need to learn a bit more") 
    st.metric(label="Similarity score", value=f"{result['similarity_score']:.2f}")
    fig = plotly_kde_distribution(result['precision_list'], position)
    st.plotly_chart(fig, use_container_width=True)
    
    recommendations = result.get("recommendations")
    if isinstance(recommendations, str):
      st.markdown(f"[Recommended course for your role]({recommendations})")
    else:
      st.write("Recommended courses by missing skills:")
      for skill, link in recommendations:
        st.markdown(f"- [{skill}]({link})")
