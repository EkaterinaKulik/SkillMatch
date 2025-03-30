import pandas as pd
import numpy as np
import json
import re
import requests
from bs4 import BeautifulSoup
import urllib.parse
import plotly.graph_objects as go
from scipy.stats import gaussian_kde

def get_links(vacancy, grade, pages=2):
    """
    Collect vacancy API URLs from HeadHunter based on position and grade.

    Parameters
    ----------
    vacancy : str
        Job title or specialization (e.g., 'Data Analyst')
    grade : str
        Seniority level or position (e.g., 'Junior', 'Middle', 'Senior')
    pages : int, optional
        Number of pages to parse (default is 2)

    Returns
    -------
    list
        A list of API URLs for the collected vacancies
    """

    links = []
    for page in range(pages):
        params = {
            "text": f"{vacancy} {grade}",
            "area": 1,  
            "page": page,
            "per_page": 100
        }

        try:
            response = requests.get("https://api.hh.ru/vacancies", params=params)
            response.raise_for_status()  
            data = response.json()
            
            if not data.get("items"):
                break
            
            for item in data["items"]:
                vacancy_url = item.get("url")
                if vacancy_url:
                    links.append(vacancy_url)


        except requests.RequestException as e:
            continue  

    return links

def get_vacancy_easyoffer(vacancy_name):
    """
    Retrieves a vacancy link by name from the easy_offer website.

    Parameters
    ----------
    vacancy_name : str
        The name of the vacancy to search for.

    Returns
    -------
    str
        The link to the vacancy (if found), otherwise an empty string.
    """
    try:
        response = requests.get('https://easyoffer.ru/')
        response.raise_for_status()
        
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        h5_tags = soup.find_all("h5", class_="card-title")
        
        for h5 in h5_tags:
            link = h5.find("a")
            if link and vacancy_name.lower() in link.text.lower():
                href = link.get("href")
                full_url = f"https://easyoffer.ru{href}"
                return full_url
        return None
    except requests.RequestException as e:
        return ""
      
def get_interview_questions(url):
    """
    Retrieves a list of interview questions from the specified link.

    Parameters
    ----------
    url : str
        The URL of the page containing interview questions.

    Returns
    -------
    list
        A list of interview questions.
    """
    try:
        page = requests.get(url)
        page.raise_for_status()

        soup = BeautifulSoup(page.text, "html.parser")
        
        tbody = soup.find("tbody")
        if not tbody:
            return []

        questions = []
        rows = tbody.find_all("tr")

        for row in rows:
            question_tag = row.find("td")
            if question_tag:
                question = question_tag.get_text(strip=True)
                questions.append(question)

        return questions
    except requests.RequestException as e:
        return ""

def calculate_precision(user_skills, vacancy_skills):
    """
    Calculates the precision score for a single vacancy.

    Precision is defined as the ratio of matched user skills to the total number of required skills in the vacancy.

    Parameters
    ----------
    user_skills : list of str
        A list of skills the applicant possesses.

    vacancy_skills : list of str
        A list of skills required for the vacancy.

    Returns
    -------
    float
        Precision score between 0 and 1. If no skills are required, returns 0.
    """

    if len(vacancy_skills) == 0:
        return 0
    intersection = len(set(user_skills).intersection(set(vacancy_skills)))
    return intersection / len(vacancy_skills)
  
def get_top_vacancies(vacancies, top_n=3):
    """
    Retrieves the top N vacancies with the highest similarity scores.

    Parameters
    ----------
    vacancies : list of dict
        A list of dictionaries representing vacancies, where each dictionary contains:
        - "similarity" : float - the similarity score
        - "alternate_url" : str - the URL to the vacancy
        - "name" : str - the title of the vacancy

    top_n : int, optional
        The number of top vacancies to return (default is 3).

    Returns
    -------
    list of dict
        A sorted list of top vacancies based on similarity.
    """

    sorted_vacancies = sorted(vacancies, key=lambda x: x["similarity"], reverse=True)

    top_vacancies = sorted_vacancies[:top_n]

    return top_vacancies

def recommend_courses(skills):
    """
    Returns course links for each skill.
    """
    recommendations = []
    for skill in skills:
        search_url = f"https://www.coursera.org/search?query={skill}"
        recommendations.append((skill, search_url))
    return recommendations

def get_missing_skills(user_skills, required_skills):
    """
    Finds missing skills not present in user profile.
    """
    return list(set(required_skills) - set(user_skills))

def generate_recommendations(vacancy_title, applicant_skills, vacancies, threshold=0.8):
    """
    Generates training recommendations based on missing skills.

    Parameters
    ----------
    vacancy_title : str
        General name of the position (e.g., 'Data Scientist')
    applicant_skills : list
        List of applicant's skills
    vacancies : list of dict
        Each vacancy is a dict with keys: name, alternate_url, vacancy_skills (list), similarity
    threshold : float
        Similarity threshold below which we consider the match weak

    Returns
    -------
    str or list
        Either a link to general training or a list of specific course links
    """
    missing_skills = set()

    for vacancy in vacancies:
        if vacancy["similarity"] < threshold:
            vacancy_miss = get_missing_skills(applicant_skills, vacancy["vacancy_skills"])
            missing_skills.update(vacancy_miss)

    if len(missing_skills) > 3:
        query = urllib.parse.quote_plus(vacancy_title)
        profession_url = f"https://www.coursera.org/search?query={query}"
        return profession_url
    elif missing_skills:
        return recommend_courses(list(missing_skills))

def vacancy_description_and_applicant_skills(vacancy_title, applicant_skills, links, threshold_ready=0.8):
    """
    Analyzes applicant skills against a set of vacancy descriptions.

    For each vacancy link provided, the function extracts required skills from the vacancy description,
    calculates precision (overlap with applicant skills), and computes the average similarity score.
    Based on the score, it either returns interview preparation content or a list of training recommendations.

    Parameters
    ----------
    vacancy_title : str
        The general title of the position (used to match with external content like interview questions or courses).

    applicant_skills : list of str
        A list of skills the applicant possesses.

    links : list of str
        A list of API links to vacancies (e.g., from https://api.hh.ru/vacancies/...).

    threshold_ready : float, optional
        Similarity threshold above which the applicant is considered ready for interview (default is 0.8).

     Returns
    -------
    dict
        A dictionary with:
        - "similarity_score": float, average precision across all vacancies
        - "precision_list": list of float, precision for each vacancy
        - "questions"/"offers" if ready
        - "recommendations" if not ready
    """

    try:
        precisions = []
        vacancies = []
        applicant_skills = [skill.lower() for skill in applicant_skills]
        
        for link in links:
            response = requests.get(link)
            response.raise_for_status()
            data = response.json()

            name = data.get("name", "")
            alt_link = data.get("alternate_url", "")
            description = data.get("description", "")
            soup = BeautifulSoup(description, "html.parser")
            plain_text = soup.get_text()
            vacancy_skills = [skill["name"].lower() for skill in data.get("key_skills", [])]
            precision = calculate_precision(applicant_skills, vacancy_skills)
            precisions.append(precision)

            vacancies.append({
                "name": name,
                "alternate_url": alt_link,
                "description": description,
                "vacancy_skills": vacancy_skills,
                "similarity": precision
            })

        similarity_score = sum(precisions) / len(precisions)
         
        result = {
            "similarity_score": similarity_score,
            "precision_list": precisions
        }

        if similarity_score >= threshold_ready:
            result["questions"] = get_interview_questions(get_vacancy_easyoffer(vacancy_title))
            result["offers"] = get_top_vacancies(vacancies)
        else:
            result["recommendations"] = generate_recommendations(vacancy_title, applicant_skills, vacancies)

        return result

    except requests.RequestException as e:
        return None
      

def plotly_kde_distribution(precision_list, vacancy_title):
    x = np.linspace(0, 1, 500)  
    kde = gaussian_kde(precision_list, bw_method=0.3)  
    y = kde(x)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode='lines', fill='tozeroy', name='KDE',
                             line=dict(color='skyblue')))
    
    fig.update_layout(
    title=f"Skill Match Distribution for {vacancy_title}",
    xaxis_title="Match Rate (Precision)",
    yaxis_title="Match Intensity",
    template="simple_white"
)
    
    return fig
