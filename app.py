import streamlit as st
import spoonacular as sp
import json
from collections import defaultdict
import os
from llama_index.llms.ollama import Ollama
from llama_index.core.llms import ChatMessage, MessageRole
import requests
import numpy as np
import httpx
from llama_index.llms.openai import OpenAI
import re
client = httpx.Client(timeout=None)

# Initialize the Spoonacular API
api = sp.API("Your_API_key")

# Set up the Streamlit interface
st.title("PrepPal")
st.write("-Your Personal Meal Planning Assistant")
st.write("Generate a personalized weekly meal plan based on your dietary preferences and calorie goals.")
# Define supported diet options
diet_options = [
    "Gluten Free",
    "Ketogenic",
    "Vegetarian",
    "Lacto-Vegetarian",
    "Ovo-Vegetarian",
    "Vegan",
    "Pescetarian",
    "Paleo",
    "Primal",
    "Low FODMAP",
    "Whole30"
]

openai_llm = OpenAI(
    api_key="your_API_key",  
    model_name="gpt-3.5-turbo",
    temperature=0.2,
    top_p=0.7,
    max_tokens=512
)
st.markdown(f"<b>AI Assistance :</b>Dear User , I am a meal planning assistant. Please tell me about your dietary preferences and calorie goals.If you don't know anything about it mention your gender, age, height and weight",unsafe_allow_html=True)
query = st.text_input("Write your query.")


system_message_content = f'''
The user may provide their age, gender, height, weight, and possibly exercise level and diet preference (e.g., vegetarian, vegan).
If exercise level is not mentioned, assume no exercise.
Use the following list of diet options to determine the appropriate dietary pattern: {diet_options}
Instructions for Output:
1.Parse the input to extract: age, gender, height, weight, exercise level (if any), and diet preference (if any).
2.If exercise level is not provided, use "sedentary (little or no exercise)" with an activity multiplier of 1.2.
3.Use the Mifflin-St Jeor equation to calculate BMR.
4.Multiply BMR by the activity factor to get TDEE (Total Daily Energy Expenditure).
5.Assume the goal is to maintain weight, unless stated otherwise.
6.Select a diet based on the calculated calories , height, weight, age and gender

Return:
1.Estimated daily calorie intake (TDEE)
2.Diet suggest based on user input and calculated calorie intake.There must be some Diet it can't be none

Return only a valid JSON object in the following format:
{{
  "cal": 1800,
  "d": "Vegetarian"
}}
Do not include explanation or code block markers like ```json.

User Input : {query}
'''

messages = [ChatMessage(role=MessageRole.SYSTEM, content=system_message_content)]    
messages.append(ChatMessage(role=MessageRole.USER, content=query))
response = openai_llm.chat(messages=messages)
raw_response = response.message.content

fixed_str = re.sub(r'([{,])\s*(\w+)\s*:', r'\1 "\2":', raw_response)           # Keys
fixed_str = re.sub(r':\s*([a-zA-Z_]+)', r': "\1"', fixed_str)             # String values

# Now fixed_str = '{ "cal": 1206, "d": "Vegetarian" }'
if not fixed_str:
    print("The JSON string is empty or null.")
else:
    data = json.loads(fixed_str)


diet = data["d"]
calories = data["cal"]



        
response = api.generate_meal_plan(timeFrame="week", diet=diet, targetCalories=calories)
meal_plan_data = response.json()
# Organize meals by day
meals_by_day = defaultdict(list)
for item in meal_plan_data.get("items", []):
    day = item.get("day")
    meal = json.loads(item.get("value", "{}"))
    meal_id = meal.get("id")
    meal_title = meal.get("title")
    meals_by_day[day].append((meal_id, meal_title))

    
# Generate meal plan upon user action
if st.button("Generate Meal Plan"):
    with st.spinner("Generating your meal plan..."):
        # Display meal plan
        for day, meals in meals_by_day.items():
            st.subheader(f"Day {day}")
            for i, (meal_id, meal_title) in enumerate(meals, 1):
                st.markdown(f"**Meal {i}: {meal_title}**")
        
                     # Fetch meal information to get the image URL
                meal_info_response = api.get_recipe_information(meal_id)
                meal_info = meal_info_response.json()

                    # Extract image URL from the meal data
                image_url = meal_info.get("image", "")

                if image_url:
                    st.image(image_url, caption=meal_title)
        
                    # Fetch recipe information
                st.write(f"Ready in: {meal_info.get('readyInMinutes', 'N/A')} minutes")
                st.write(f"Servings: {meal_info.get('servings', 'N/A')}")
                st.write("Ingredients:")
                for ingredient in meal_info.get('extendedIngredients', []):
                    st.write(f"- {ingredient.get('original', '')}")
                st.write("Instructions:")
                instructions = meal_info.get('instructions', 'No instructions provided.')
                st.markdown(instructions, unsafe_allow_html=True)

def get_shopping_list(meals_by_day, api):
    shopping_list = defaultdict(list)

    for day, meals in meals_by_day.items():
        for meal_id, _ in meals:
            response = api.get_recipe_information(meal_id)
            meal_info = response.json()
            for ingredient in meal_info.get("extendedIngredients", []):
                name = ingredient.get("name", "").lower()
                amount = ingredient.get("amount", 0)
                unit = ingredient.get("unit", "")
                shopping_list[name].append((amount, unit))
    
    # Combine quantities for the same item
    consolidated_list = {}
    for name, entries in shopping_list.items():
        total_amount = sum(entry[0] for entry in entries)
        unit = entries[0][1] if entries else ""
        consolidated_list[name] = f"{total_amount:.2f} {unit}"

    return consolidated_list


# Add shopping list generation after meal plan
if st.button("Get Shopping List"):
    with st.spinner("Fetching shopping list..."):
        shopping_list = get_shopping_list(meals_by_day, api)
        st.subheader("🛒 Shopping List")
        for item, quantity in shopping_list.items():
            st.write(f"- {item.title()}: {quantity}")

              


