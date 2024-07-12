# import required libraries
import pandas as pd
import numpy as np
import _pickle as cPickle
import pickle
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn import preprocessing
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.metrics import mean_squared_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import cross_validate
from sklearn.model_selection import KFold
import json
import os
from PIL import Image
from io import BytesIO
import base64
from scipy.optimize import minimize
# import pycaret
# from pycaret.regression import *

from sklearn.base import clone 
#import seaborn as sns
import matplotlib.pyplot as plt
# sns.set_style("whitegrid")
# sns.set(rc = {'figure.figsize':(15, 10)})

import time
import shap 
import xgboost
import optuna
shap.initjs()
from IPython.display import display, HTML
from IPython.core.interactiveshell import InteractiveShell
InteractiveShell.ast_node_interactivity = "all"
import warnings
warnings.filterwarnings("ignore")
import streamlit as st
from scipy.optimize import curve_fit
import io
import msal
import requests

page = "Optimise total budget"
# config parameters
market = 'Japan'
model_type = 'Consumables'
retailer = 'FamilyMart'

# =============================   SSO Login   ===================================================

# Microsoft Azure AD configurations
CLIENT_ID = "15dfcfc0-38a3-4719-911d-19bd250e1e27"
CLIENT_SECRET = "n9u8Q~reHgfVJrNikVorNPq4KLvS_J0JjH69vbhO"
AUTHORITY = "https://login.microsoftonline.com/68421f43-a2e1-4c77-90f4-e12a5c7e0dbc"
SCOPE = ["User.Read", "Mail.Read"]
REDIRECT_URI = "https://mtflpjpww5ms3yv9galhh9.streamlit.app/" # This should match your Azure AD app configuration

# Initialize MSAL application
app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY,
    client_credential=CLIENT_SECRET)

def get_auth_url():
    return app.get_authorization_request_url(SCOPE, redirect_uri=REDIRECT_URI)

def get_token_from_code(code):
    try:
        result = app.acquire_token_by_authorization_code(code, SCOPE, redirect_uri=REDIRECT_URI)
        if "access_token" in result:
            return result["access_token"]
        else:
            st.error(f"Failed to acquire token. Error: {result.get('error')}")
            st.error(f"Error description: {result.get('error_description')}")
            return None
    except Exception as e:
        st.error(f"An exception occurred: {str(e)}")
        return None

#def get_user_info(access_token):
    #headers = {'Authorization': f'Bearer {access_token}'}
    #response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
    #return response.json()

def login():
    auth_url = get_auth_url()
    st.markdown(f'[Login with Microsoft]({auth_url})')

def get_user_info(access_token):
       headers = {'Authorization': f'Bearer {access_token}'}
       response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
       user_info = response.json()
       return user_info.get('mail') or user_info.get('userPrincipalName')



# =============================   FUNCTIONS   ===================================================

# Function to load data based on user input
def load_data(market, model_type, retailer):
    file_path = "C:/Users/Technology/Desktop/tasks/mmm_random_forest_shap/bat_mmm_models/data/" + market + '/' + model_type + '/' + f"{retailer}.xlsx"
    if os.path.exists(file_path):
        df = pd.read_excel(file_path, sheet_name='Data')
        coldf = pd.read_excel(file_path, sheet_name='FM_cons_columns')
        return df, coldf
    else:
        st.error(f"File not found: {file_path}")
        return None

# Function to display model statistics
def display_statistics(data, model, X, rsq, md, nt):
    st.markdown('<div class="section-header">Model Statistics</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # Number of points (rows) in the dataset
    num_points = len(data)
    st.write(f"Number of points (rows) in the dataset: {num_points}")
    
    # Number of independent variables
    num_independent_vars = X.shape[1]
    st.write(f"Number of independent variables: {num_independent_vars}")
    
    # Degrees of freedom
    degrees_of_freedom = num_points - num_independent_vars
    st.write(f"Degrees of freedom: {degrees_of_freedom}")
    
    # R squared %
    st.write(f"R squared (%): {rsq:.2f}")
    
    # Max depth
    st.write(f"Max depth: {md}")
    
    # Number of trees
    st.write(f"Number of trees: {nt}")
    
    # Number of nodes
    num_nodes = sum(estimator.tree_.node_count for estimator in model.estimators_.flatten())
    st.write(f"Number of nodes: {num_nodes}")
    
    # Feature importance table
    st.markdown('<div class="section-header">Feature Importance</div>', unsafe_allow_html=True)
    feature_importance = pd.DataFrame({
        'Feature': X.columns,
        'Importance': model.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    st.table(feature_importance.style.format({"Importance": "{:.2f}"}))

# Function to generate download link for DataFrame
def generate_excel_download_link(df, file_name, text):
    towrite = BytesIO()
    df.to_excel(towrite, index=False, engine='xlsxwriter')
    towrite.seek(0)
    b64 = base64.b64encode(towrite.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{file_name}.xlsx">{text}</a>'
    return href

def to_excel(df):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    writer.save()
    processed_data = output.getvalue()
    return processed_data

 # Function to format large numbers
def format_number(num):
    if abs(num) >= 1e6:
        return f'{num/1e6:.1f}M'
    elif abs(num) >= 1e3:
        return f'{num/1e3:.1f}K'
    else:
        return f'{num:.1f}'

def hill_function2(x, slope, carryover, power, max_uplift):
    adjusted_x = carryover * x
    return max_uplift * (adjusted_x ** power) / (slope ** power + adjusted_x ** power)

def calculate_incremental_revenue(total_spend, media_cont_df, saturation_params):
    new_total_revenue = 0
    new_total_cont = 0
    act_total_revenue=0
    act_total_cont=0
    perc_upl_list=[]
    
    
    for channel, pr in saturation_params.iterrows():
        perc_upl = hill_function2(total_spend[channel], pr['slope'], pr['carryover'], pr['power'], pr['max_uplift'])
        actual_media_cont = media_cont_df[channel].values[0]
        new_media_cont = actual_media_cont + ((perc_upl*actual_media_cont)/100)
        actual_media_rev = (actual_media_cont*23.94)/174.88
        new_media_rev = (new_media_cont*23.94)/174.88
        new_total_revenue += new_media_rev
        new_total_cont += new_media_cont
        act_total_revenue += actual_media_rev
        act_total_cont += actual_media_cont
        perc_upl_list.append(perc_upl)
        
    return new_total_revenue

# Function to infer parameters and plot saturation curves for media channels
def optimise_saturation_curves_params(df, dff_fin):
    
    # prepare dataframe with spend and contribution
    curvedf = pd.DataFrame(
    {'Spend_CVS': df['jp_bat_CVS_FM-total_exc_enabling_inv'], 'Cont_CVS': dff_fin['jp_bat_CVS_FM-total_exc_enabling_inv_adstocked'],
     'Spend_NMP': df['jp_bat_NMP_without_enabling_inv'], 'Cont_NMP': dff_fin['jp_bat_NMP_without_enabling_inv_adstocked'],
     'Spend_One2One': df['jp_bat_one2one_approach'], 'Cont_One2One': dff_fin['jp_bat_one2one_approach_adstocked'],
     'Spend_EDM': df['jp_bat_EDM_total_inv'], 'Cont_EDM': dff_fin['jp_bat_EDM_total_inv_adstocked'],
     'Spend_OOH': df['jp_bat_OOH_reach'], 'Cont_OOH': dff_fin['jp_bat_OOH_reach_adstocked'],
     'Spend_Social': df['jp_bat_social_total_inv'], 'Cont_Social': dff_fin['jp_bat_social_total_inv_adstocked'],
     'Spend_Horeca': df['jp_bat_horeca-events_total_inv'], 'Cont_Horeca': dff_fin['jp_bat_horeca-events_total_inv_adstocked'],
     'Spend_ConnectedTV': df['jp_bat_ConnectedTV_inv'], 'Cont_ConnectedTV': dff_fin['jp_bat_ConnectedTV_impressions_adstocked'],
     'Spend_DigDisp': df['jp_bat_DigitalDisplay_inv'], 'Cont_DigDisp': dff_fin['jp_bat_DigitalDisplay_impressions_adstocked'],
     'Spend_ProgDisp': df['jp_bat_ProgrammaticDisplay_inv'], 'Cont_ProgDisp': dff_fin['jp_bat_ProgrammaticDisplay_impressions_adstocked'],
     'Spend_ProgVid': df['jp_bat_ProgrammaticVideo_inv'], 'Cont_ProgVid': dff_fin['jp_bat_ProgrammaticVideo_impressions_adstocked'],
     'Spend_SocialDisp': df['jp_bat_SocialDisplay_inv'], 'Cont_SocialDisp': dff_fin['jp_bat_SocialDisplay_impressions_adstocked']
     })
    
    # Infer hill function parameters
    channels = ['CVS', 'NMP','One2One','EDM','OOH','Social','Horeca','ConnectedTV','DigDisp','ProgDisp','ProgVid','SocialDisp']

    # Fit the Hill function to each channel
    params = {}
    param_names = ['slope', 'carryover', 'power', 'max_uplift']
    param_df = pd.DataFrame(columns=param_names)
    
    for channel in channels:
        spend = np.array(list(curvedf[f'Spend_{channel}']))
        contribution = np.array(list(curvedf[f'Cont_{channel}']))
        
        uplift_percentage = (contribution / curvedf.max().mean())*100
        max_spend = max(spend)
        max_uplift_percentage = max(uplift_percentage)
#        min_uplift_percentage = min(uplift_percentage)
    
        initial_guess = [max_spend, 0.1, 1, max_uplift_percentage/2]
        param_bounds = ([0, 0, 0, 0], [max_spend, 100, 1, max_uplift_percentage])
        popt, covariance = curve_fit(hill_function2, spend, uplift_percentage, p0=initial_guess, bounds=param_bounds, maxfev=10000)
        params[channel] = popt
        param_df.loc[channel] = popt
    
    # Create a DataFrame to store the spend and calculated uplift percentages
    spend_values = np.arange(0, max(spend), 1000)
    # Initialize a dictionary to store the calculated uplift percentages for each channel
    uplift_data = {'Spend': spend_values}
    
    for channel in params.keys():
        slope, carryover, power, max_uplift = params[channel]
        uplift_percentages = hill_function2(spend_values, slope, carryover, 1, max_uplift)
        uplift_data[f'Uplift_Percentage_Channel_{channel}'] = uplift_percentages
    
    # Create a DataFrame from the uplift data
    uplift_df = pd.DataFrame(uplift_data)
    
    # Display the DataFrame
    uplift_df = uplift_df.replace(np.inf,0)
    uplift_df = uplift_df.replace(-np.inf,0)
    uplift_df.fillna(0, inplace=True)
    
    return param_df, uplift_df

# Function to optimize media spend
def optimize_media_spend(total_budget, media_channels, min_spend, max_spend, saturation_params):
    def objective(spends):
        total_effect = 0
        for i, channel in enumerate(media_channels):
            spend = spends[i]
            slope, carryover, power, max_uplift = saturation_params.loc[channel]
            effect = max_uplift * (1 - np.exp(-slope * (spend ** power))) * carryover
            total_effect += effect
        return -total_effect
    
    constraints = [{'type': 'ineq', 'fun': lambda x: total_budget - np.sum(x)},
                   {'type': 'ineq', 'fun': lambda x: x - min_spend},
                   {'type': 'ineq', 'fun': lambda x: max_spend - x}]
    
    #initial_guess = [(min_spend[i] + max_spend[i]) / 2 for i in range(len(media_channels))]
    
    total_budget = sum(max_spend)
    initial_guess_uniform = [total_budget / len(max_spend) for _ in range(len(max_spend))]
    
    result = minimize(objective, initial_guess_uniform, constraints=constraints, method='SLSQP')
    
    if result.success:
        optimized_spend = result.x
        return {media_channels[i]: optimized_spend[i] for i in range(len(media_channels))}
    else:
        st.error("Optimization failed. Please check your inputs.")
        return None

# Function to display total spend per channel per year
def display_spend_plot(spend_data):
    fig, ax = plt.subplots(figsize=(10, 6))
    spend_data.plot(kind='bar', stacked=True, ax=ax)
   # ax.set_title("Total Spend per Year")
    ax.set_xlabel("Year")
    ax.set_ylabel("Total Spend")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x/1e6)}M"))
    st.pyplot(fig)

# Function to display optimised total spend per channel per year
def display_optimized_spend_plot(optimized_spend):
    fig, ax = plt.subplots(figsize=(20, 20))
    spend_series = pd.Series(optimized_spend)
    spend_series.plot(kind='barh', ax=ax)
    plt.rcParams.update({'font.size': 30})
    # Annotate each bar with the spend value
    for index, value in enumerate(spend_series):
        ax.text(value, index, f"{value/1e6:.1f}M", va='center', ha='left', color='black', fontweight='bold')

    ax.set_xlabel("Optimized Spend", fontsize = 30)
    ax.set_ylabel("Channel", fontsize = 30)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x/1e6)}M"))
    st.pyplot(fig)
    
# Function to display the weekly optimised spend
def display_optimized_weekly_spend_plot(optimized_weekly_spend):
    fig, ax = plt.subplots(figsize=(20, 12))
    optimized_weekly_spend.plot(kind='area', stacked=True, ax=ax)
    ax.set_title("Optimized Weekly Spend per Media Channel")
    ax.set_xlabel("Week")
    ax.set_ylabel("Spend (in Millions)")
    ax.set_xticks(range(len(optimized_weekly_spend)))
    ax.set_xticklabels([f"{i}" for i in range(len(optimized_weekly_spend))])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x/1e6)}M"))
    st.pyplot(fig)   

# Function to display actual and optimised spend in a table
def display_comparison_table(actual_spend, optimized_spend, media_cont_df, saturation_params):
    actual_spend_series = pd.Series(actual_spend)
    optimized_spend_series = pd.Series(optimized_spend)
    
    act_rev_list = []
    opt_rev_list = []
    rev_pct_list = []
    
    for channel, pr in saturation_params.iterrows():
        perc_upl = hill_function2(optimized_spend[channel], pr['slope'], pr['carryover'], pr['power'], pr['max_uplift'])
        actual_media_cont = media_cont_df[channel].values[0]
        new_media_cont = actual_media_cont + ((perc_upl*actual_media_cont)/100)
        ar = (actual_media_cont*23.94)/174.88
        nr = (new_media_cont*23.94)/174.88
        pct = ((nr-ar)/ar)*100
        act_rev_list.append(ar)
        opt_rev_list.append(nr)
        rev_pct_list.append(pct)


    #actual_incr_revenue = calculate_incremental_revenue(actual_spend, saturation_params)
    #optimized_incr_revenue = calculate_incremental_revenue(optimized_spend, saturation_params)

    comparison_df = pd.DataFrame({
        'Act Spend': actual_spend_series,
        'Act Incr Rev': act_rev_list,
        'Opt Spend': optimized_spend_series,
        'Opt Incr Rev': opt_rev_list,
        '% Change Rev': rev_pct_list
    })
    
    comparison_df.index.name = 'Media Channel'
    comparison_df['Act Spend'] = comparison_df['Act Spend'].apply(lambda x: f"{x/1e6:.2f}M")
    comparison_df['Act Incr Rev'] = comparison_df['Act Incr Rev'].apply(lambda x: f"{x/1e6:.2f}M")
    comparison_df['Opt Spend'] = comparison_df['Opt Spend'].apply(lambda x: f"{x/1e6:.2f}M")
    comparison_df['Opt Incr Rev'] = comparison_df['Opt Incr Rev'].apply(lambda x: f"{x/1e6:.2f}M")
    comparison_df['% Change Rev'] = comparison_df['% Change Rev'].apply(lambda x: f"{x:.2f}%")

    comparison_df = comparison_df.style.applymap(lambda x: 'background-color: #ffcccc' if isinstance(x, float) and x < 0 else 'background-color: #ccffcc', subset=['% Change Rev'])
    return comparison_df
   

def logistic_function(x, L, k, x0):
    return L / (1 + np.exp(-k * (x - x0)))

# Function to calculate the display the impact of increase in distribution points
def display_distribution_impact(weekly_spend_data, distribution_change):
    # Aggregate yearly data for 2022 and 2023
    weekly_data = weekly_spend_data.groupby(weekly_spend_data['Date'].dt.year).sum()

    # Calculate the change in aggregated yearly distribution contribution
    change_in_contribution = abs(((weekly_data.loc[2023, 'dist_cont'] - weekly_data.loc[2022, 'dist_cont']) / weekly_data.loc[2022, 'dist_cont']))

    # Calculate the change in average distribution raw values
 #   avg_distribution_2022 = weekly_spend_data[weekly_spend_data['date'].dt.year == 2022]['Distribution Points'].mean()
 #   avg_distribution_2023 = weekly_spend_data[weekly_spend_data['date'].dt.year == 2023]['Distribution Points'].mean()
    #change_in_avg_distribution = (avg_distribution_2023 - avg_distribution_2022) / avg_distribution_2022

    # Infer the slope based on changes
    x_data = np.array([0, 50, 100])  # Change in distribution points: 0%, 50%, 100%
    y_data = np.array([0, change_in_contribution * 0.5, change_in_contribution])  # Corresponding change in contribution
    
    popt, pcov = curve_fit(logistic_function, x_data, y_data, maxfev=10000)
    
    # Generate data for smoother logistic curve
    x_curve = np.linspace(1, 10, 10)
    y_curve = logistic_function(x_curve, *popt)
    
    # Plot the logistic curve
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(x_curve, y_curve, label='Logistic Curve')
    ax.set_title("Distribution Curve")
    ax.set_xlabel("Increase in Distribution Points (%)")
    ax.set_ylabel("Change in Contribution ")
    ax.legend()
    st.pyplot(fig)
    
    # Create and display the incremental uplift table
    uplift_table = pd.DataFrame({
        "Distribution Points Increase (%)": x_curve,
        "Change in Contribution": y_curve
    })
    st.write("Incremental Uplift Table")
    st.table(uplift_table)

# Function to calculate the display the impact of increase in price
def display_price_impact(weekly_spend_data, price_change):
    # Aggregate yearly data for 2022 and 2023
    weekly_data = weekly_spend_data.groupby(weekly_spend_data['Date'].dt.year).sum()

    # Calculate the change in aggregated yearly distribution contribution
    change_in_contribution = ((weekly_data.loc[2023, 'price_cont'] - weekly_data.loc[2022, 'price_cont']) / weekly_data.loc[2022, 'price_cont'])

    # Calculate the change in average distribution raw values
 #   avg_distribution_2022 = weekly_spend_data[weekly_spend_data['date'].dt.year == 2022]['Distribution Points'].mean()
 #   avg_distribution_2023 = weekly_spend_data[weekly_spend_data['date'].dt.year == 2023]['Distribution Points'].mean()
    #change_in_avg_distribution = (avg_distribution_2023 - avg_distribution_2022) / avg_distribution_2022

    # Infer the slope based on changes
    x_data = np.array([0, 50, 100])  # Change in price points: 0%, 50%, 100%
    y_data = np.array([0, change_in_contribution * 0.5, change_in_contribution])  # Corresponding change in contribution
    
    popt, pcov = curve_fit(logistic_function, x_data, y_data, maxfev=10000)
    
    # Generate data for smoother logistic curve
    x_curve = np.linspace(1, 10, 10)
    y_curve = logistic_function(x_curve, *popt)
    
    # Plot the logistic curve
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(x_curve, y_curve)
    ax.set_title("Price Curve")
    ax.set_xlabel("Increase in Price (%)")
    ax.set_ylabel("Change in Contribution")
    ax.legend()
    st.pyplot(fig)
    
    # Create and display the incremental uplift table
    uplift_table = pd.DataFrame({
        "Price Increase (%)": x_curve,
        "Change in Contribution": y_curve
    })
    st.write("Incremental Uplift Table")
    st.table(uplift_table)
















# =================================  END OF FUNCTIONS  ======================================

def main():
    
    st.set_page_config(layout="wide")
    #=========================== Apply custom CSS styles  ==================================
    st.markdown(
        """
        <style>
        .header {
            color: black;
        }
        .header-title {
            font-size: 2em;
            font-weight: bold;
        }
        section[data-testid="stSidebar"] {
            width: 300px !important;
            }

        .sidebar .sidebar-content {
            background-color: #1f4e79;
            color: white;
        }
        .sidebar .sidebar-content select, .sidebar .sidebar-content input, .sidebar .sidebar-content button {
            color: white;
        }
        .sidebar .sidebar-content .stButton button {
            background-color: #1f4e79;
            color: white;
        }
        .sidebar .sidebar-content .stButton button:hover {
            background-color: #163a56;
            color: white;
        }
        .main-content {
            display: flex;
            flex-direction: row;
            justify-content: space-between;
        }
        .section-header {
            font-size: 1.5em;
            margin-top: 20px;
            margin-bottom: 10px;
            color: #333333;
            }
        .divider {
            border-top: 2px solid #1f4e79;
            margin-top: 20px;
            margin-bottom: 20px;
            }
        .scaling-input {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
            gap: 10px;
        }
        .scaling-input input {
            width: 100%;
            .sidebar-header {
            font-size: 1.8em;
            font-weight: bold;
            margin-bottom: 20px;
        }
        .user-info {
            position: absolute;
            top: 10px;
            right: 10px;
            display: flex;
            align-items: center;
        }
        .user-info span {
            margin-right: 10px;
        }
        .user-info button {
            background-color: #1f4e79;
            color: white;
            border: none;
            padding: 5px 10px;
            cursor: pointer;
            border-radius: 5px;
        }
        .user-info button:hover {
            background-color: #163a56;
        }
        .download-btn {
            background-color: #1f4e79;
            color: white;
            border: none;
            padding: 10px;
            cursor: pointer;
            border-radius: 5px;
            font-size: 16px;
        }
        .download-btn:hover {
            background-color: #163a56;
        }
        .download-btn i {
            margin-right: 5px;
        }
        section[data-testid="stMetricValue"] {
            justify-content: center;
        }
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
        .download-icon {
            font-size: 1.5em;
            color: #000000;
            cursor: pointer;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
            
    #=========================== User Info Top Right ==================================
    #Top right user info
    # st.markdown(
    #     """
    #     <div class="user-info">
    #         <span>user@example.com</span>
    #         <button>Logout</button>
    #     </div>
    #     """,
    #     unsafe_allow_html=True
    # )
    
    #=========================== Add logo on sidebar  ==================================
    
    # Path to the logo on your local machine
    logo_path = r"new_logo_rembg.png"
    
    # Display the logo at the top right corner
    logo_img = Image.open(logo_path)
    logo_img = logo_img.resize((50, 50))
    st.sidebar.image(logo_img, use_column_width=False)
    
    
    #=========================== Sidebar Inputs  ==================================
    # Initialize session state if not already initialized
    if "inputs" not in st.session_state:
        st.session_state.inputs = {}
    
    st.sidebar.header("Input Parameters")
    market = st.sidebar.selectbox("Select Market", ["Japan", "Canada", "Germany"])
    model_type = st.sidebar.selectbox("Select Model Type", ["Consumables", "Devices"])
    retailer = st.sidebar.selectbox("Select Retailer", ["FamilyMart", "Lawson"])

    st.sidebar.markdown("## Menu")
    page = "Optimise total budget"
    if st.sidebar.button("📊 Optimise total budget"):
        page = "Optimise total budget"
    if st.sidebar.button("⏱️ Optimise weekly timing"):
        page = "Optimise weekly timing"
    if st.sidebar.button("💲 Pricing & distribution scenarios"):
        page = "Pricing & distribution scenarios"
    
    st.sidebar.markdown("## About")
    if st.sidebar.button("🔍 Attribution Results"):
        page = "Attribution Results"
    if st.sidebar.button("📈 Performance Insights"):
        page = "Performance Insights"
    st.sidebar.markdown('<div class="scaling-input">', unsafe_allow_html=True)   
    
    #=========================== Optimise total budget page ==================================
    if page == "Optimise total budget":
             logout_container = st.container()
             st.title("Streamlit App with Microsoft SSO")
             #Global variables
             # Initialize session state variables
    
    
             # Initialize session state variables
             if 'access' not in st.session_state:
                      st.session_state.access = False
                      
             if 'login_clicked' not in st.session_state:
                      st.session_state.login_clicked = False

             if 'user_email' not in st.session_state:
                st.session_state.user_email = None
        
             if not st.session_state.access:                  
                                        login()
                                        # Check for authorization code in URL
                                        params = st.experimental_get_query_params()
                                        if "code" in params:
                                                 code = params["code"][0]
                                                 token = get_token_from_code(code)
                                                 if token:
                                                          st.session_state.access_token = token
                                                          st.session_state.user_email = get_user_info(st.session_state.access_token)
                                                          st.experimental_set_query_params()
        
                                                 st.markdown("""
                                                        <div class="header">
                                                            <div class="header-title">Optimise Total Budget</div>
                                                        </div>
                                                    """, unsafe_allow_html=True)
                                                
                                                  # Load data
                                                 df = pd.read_excel(r"BAT Japan model - 9.3_MP_ownprice (1).xlsx", sheet_name='Data')
                                                 dff_fin = pd.read_excel(r"bat_japan_fm_cons_cont_v2.xlsx")
                                                 params = pd.read_excel(r"media_saturation_params.xlsx")
                                                    
                                                 weekly_spend_df = pd.DataFrame(
                                                 {'CVS': df['jp_bat_CVS_FM-total_exc_enabling_inv']/174.88, 
                                                 'NMP': df['jp_bat_NMP_without_enabling_inv']/174.88, 
                                                 'One2One': df['jp_bat_one2one_approach']/174.88, 
                                                 'EDM': df['jp_bat_EDM_total_inv']/174.88, 
                                                 'OOH': df['jp_bat_OOH_reach']/174.88, 
                                                 'Social': df['jp_bat_social_total_inv']/174.88, 
                                                 'Horeca': df['jp_bat_horeca-events_total_inv']/174.88, 
                                                 'ConnectedTV': df['jp_bat_ConnectedTV_inv']/174.88, 
                                                 'DigDisp': df['jp_bat_DigitalDisplay_inv']/174.88, 
                                                 'ProgDisp': df['jp_bat_ProgrammaticDisplay_inv']/174.88, 
                                                 'ProgVid': df['jp_bat_ProgrammaticVideo_inv']/174.88, 
                                                 'SocialDisp': df['jp_bat_SocialDisplay_inv']/174.88, 
                                                 'Year': df['y']
                                                })
                                                
                                                 media_contr_df = pd.DataFrame(
                                                 {'CVS': [dff_fin['jp_bat_CVS_FM-total_exc_enabling_inv_adstocked'].sum()],
                                                 'NMP': [dff_fin['jp_bat_NMP_without_enabling_inv_adstocked'].sum()],
                                                 'One2One': [dff_fin['jp_bat_one2one_approach_adstocked'].sum()],
                                                 'EDM': [dff_fin['jp_bat_EDM_total_inv_adstocked'].sum()],
                                                 'OOH': [dff_fin['jp_bat_OOH_reach_adstocked'].sum()],
                                                 'Social': [dff_fin['jp_bat_social_total_inv_adstocked'].sum()],
                                                 'Horeca': [dff_fin['jp_bat_horeca-events_total_inv_adstocked'].sum()],
                                                 'ConnectedTV': [dff_fin['jp_bat_ConnectedTV_impressions_adstocked'].sum()],
                                                 'DigDisp': [dff_fin['jp_bat_DigitalDisplay_impressions_adstocked'].sum()],
                                                 'ProgDisp': [dff_fin['jp_bat_ProgrammaticDisplay_impressions_adstocked'].sum()],
                                                 'ProgVid': [dff_fin['jp_bat_ProgrammaticVideo_impressions_adstocked'].sum()],
                                                 'SocialDisp': [dff_fin['jp_bat_SocialDisplay_impressions_adstocked'].sum()]
                                                })
                                                 total_spend_df = pd.DataFrame(weekly_spend_df.groupby('Year')[list(weekly_spend_df.columns)[:-1]].sum())
                                                 media_channels = ['CVS', 'NMP','One2One','EDM','OOH','Social','Horeca','ConnectedTV','DigDisp','ProgDisp','ProgVid','SocialDisp']
                                                 params.index=media_channels
                                                
                                                 # Print the main metrics
                                                 total_spend = total_spend_df.loc[2023].sum()
                                                 incremental_revenue = (media_contr_df.sum().sum()*23.94)/174.88
                                                 incremental_gross_margin = incremental_revenue * 0.3  # Assuming 30% gross margin
                                                 col1, col2, col3 = st.columns(3)
                                                 col1.metric(label="Total Spend in 2023 (GBP)", value=f"£{total_spend/1e6:.2f}M")
                                                 col2.metric(label="Incremental Revenue (GBP)", value=f"£{incremental_revenue/1e6:.2f}M")
                                                 col3.metric(label="Incremental Gross Margin (GBP)", value=f"£{incremental_gross_margin/1e6:.2f}M")
                                                 st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                                    
                                                 # Ask user to enter total budget and channel spend constraints
                                                 st.subheader("Optimization Inputs")
                                                 budget_change_pct = st.number_input("Budget % Change", value=st.session_state.inputs.get("budget_change_pct", 0), key="budget_change_pct")
                                                 total_budget = total_spend_df.loc[2023].sum() * (1 + budget_change_pct / 100)  
                                                
                                                 min_spend = {}
                                                 max_spend = {}
                                                
                                                 cols = st.columns(3)
                                                 #cols[0].markdown("### Channel")
                                                 cols[0].markdown("### Min (%)")
                                                 cols[1].markdown("### Max (%)")
                                                 cols[2].markdown("### Last Year")
                                    
                                                 for channel in media_channels:
                                                     col1, col2, col3 = st.columns(3)
                                                     # with col1:
                                                     #     col1.markdown(f"**{channel}**")
                                                     with col1:
                                                         min_spend[channel] = st.text_input(f"{channel}_Min", value=st.session_state.inputs.get(f"min_spend_{channel}", 0), key=f"min_spend_{channel}")
                                                     with col2:
                                                         max_spend[channel] = st.text_input(f"{channel}_Max", value=st.session_state.inputs.get(f"max_spend_{channel}", 0), key=f"max_spend_{channel}")
                                                     with col3:
                                                         col3.markdown(f"£{round(total_spend_df.loc[2023, channel]/1e6,1)}M")


                                                 if st.button("Optimize Spend"):
                                                     st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                                                     min_spend = {channel: total_spend_df.loc[2023, channel] * (1 + float(min_spend[channel]) / 100) for channel in media_channels if min_spend[channel]}
                                                     max_spend = {channel: total_spend_df.loc[2023, channel] * (1 + float(max_spend[channel]) / 100) for channel in media_channels if max_spend[channel]}
                                                     # min_spend = {k: float(v) for k, v in min_spend.items() if v}
                                                     # max_spend = {k: float(v) for k, v in max_spend.items() if v}
                                                     optimized_spend = optimize_media_spend(total_budget, media_channels, list(min_spend.values()), list(max_spend.values()), params)
                                                     if optimized_spend:
                                                         # Print the optimised metrics
                                                         new_total_spend = sum(optimized_spend.values())
                                                         new_incremental_revenue = calculate_incremental_revenue(optimized_spend, media_contr_df, params)
                                                         new_incremental_gross_margin = new_incremental_revenue * 0.3  # Assuming 30% gross margin
                                                         col1, col2, col3 = st.columns(3)
                                                         col1.metric(label="New Total Spend (GBP)", value=f"£{new_total_spend/1e6:.2f}M")
                                                         col2.metric(label="Optimised Incremental Revenue (GBP)", value=f"£{new_incremental_revenue/1e6:.2f}M")
                                                         col3.metric(label="Optimised Incremental Gross Margin (GBP)", value=f"£{new_incremental_gross_margin/1e6:.2f}M")
                                                         #st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                                                         #st.markdown('<div class="section-header">Optimized Total Spend</div>', unsafe_allow_html=True)                
                                                        
                                                         actual_spend = total_spend_df.loc[2023].to_dict()
                                                         col1, col2 = st.columns(2)
                                                         with col1:
                                                            opt_results_df = display_comparison_table(actual_spend, optimized_spend, media_contr_df, params)
                                                            st.dataframe(opt_results_df, height=320)
                                                            
                                                            # Display download button
                                                            opt_results_df_download = to_excel(opt_results_df)
                                                            b64 = base64.b64encode(opt_results_df_download).decode()
                                                            st.markdown(f"""
                                                            <a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="optimised_spend.xlsx">
                                                                <i class="fas fa-download download-icon"></i>
                                                            </a>
                                                            """, unsafe_allow_html=True)
                                                        
                                                            # Add download button for optimal spend
                                                            #st.markdown(generate_excel_download_link(opt_results_df, "optimal_spend", "Download"), unsafe_allow_html=True)
                                                            # st.markdown(
                                                            #     """
                                                            #     <div class="results-section">
                                                            #         <button class="download-btn">
                                                            #             <i class="fa fa-download"></i>
                                                            #         </button>
                                                            #     </div>
                                                            #     """,
                                                            #     unsafe_allow_html=True
                                                            # )
                                                            # Include Font Awesome for download icon
                                                            st.markdown(
                                                                """
                                                                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
                                                                """,
                                                                unsafe_allow_html=True
                                                            )
                                                         with col2:
                                                            display_optimized_spend_plot(optimized_spend)
                                                 st.session_state.access = True
                                                 st.experimental_rerun()
    
             else:
                # User is logged in, show content and logout button
                st.write("You are logged in!")
                st.markdown("""
                <div class="header">
                <div class="header-title">Optimise Total Budget</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Load data
                df = pd.read_excel(r"BAT Japan model - 9.3_MP_ownprice (1).xlsx", sheet_name='Data')
                dff_fin = pd.read_excel(r"bat_japan_fm_cons_cont_v2.xlsx")
                params = pd.read_excel(r"media_saturation_params.xlsx")
                
                weekly_spend_df = pd.DataFrame(
                {'CVS': df['jp_bat_CVS_FM-total_exc_enabling_inv']/174.88, 
                'NMP': df['jp_bat_NMP_without_enabling_inv']/174.88, 
                'One2One': df['jp_bat_one2one_approach']/174.88, 
                'EDM': df['jp_bat_EDM_total_inv']/174.88, 
                'OOH': df['jp_bat_OOH_reach']/174.88, 
                'Social': df['jp_bat_social_total_inv']/174.88, 
                'Horeca': df['jp_bat_horeca-events_total_inv']/174.88, 
                'ConnectedTV': df['jp_bat_ConnectedTV_inv']/174.88, 
                'DigDisp': df['jp_bat_DigitalDisplay_inv']/174.88, 
                'ProgDisp': df['jp_bat_ProgrammaticDisplay_inv']/174.88, 
                'ProgVid': df['jp_bat_ProgrammaticVideo_inv']/174.88, 
                'SocialDisp': df['jp_bat_SocialDisplay_inv']/174.88, 
                'Year': df['y']
                })
                
                media_contr_df = pd.DataFrame(
                {'CVS': [dff_fin['jp_bat_CVS_FM-total_exc_enabling_inv_adstocked'].sum()],
                'NMP': [dff_fin['jp_bat_NMP_without_enabling_inv_adstocked'].sum()],
                'One2One': [dff_fin['jp_bat_one2one_approach_adstocked'].sum()],
                'EDM': [dff_fin['jp_bat_EDM_total_inv_adstocked'].sum()],
                'OOH': [dff_fin['jp_bat_OOH_reach_adstocked'].sum()],
                'Social': [dff_fin['jp_bat_social_total_inv_adstocked'].sum()],
                'Horeca': [dff_fin['jp_bat_horeca-events_total_inv_adstocked'].sum()],
                'ConnectedTV': [dff_fin['jp_bat_ConnectedTV_impressions_adstocked'].sum()],
                'DigDisp': [dff_fin['jp_bat_DigitalDisplay_impressions_adstocked'].sum()],
                'ProgDisp': [dff_fin['jp_bat_ProgrammaticDisplay_impressions_adstocked'].sum()],
                'ProgVid': [dff_fin['jp_bat_ProgrammaticVideo_impressions_adstocked'].sum()],
                'SocialDisp': [dff_fin['jp_bat_SocialDisplay_impressions_adstocked'].sum()]
                })
                total_spend_df = pd.DataFrame(weekly_spend_df.groupby('Year')[list(weekly_spend_df.columns)[:-1]].sum())
                media_channels = ['CVS', 'NMP','One2One','EDM','OOH','Social','Horeca','ConnectedTV','DigDisp','ProgDisp','ProgVid','SocialDisp']
                params.index=media_channels
                
                # Print the main metrics
                total_spend = total_spend_df.loc[2023].sum()
                incremental_revenue = (media_contr_df.sum().sum()*23.94)/174.88
                incremental_gross_margin = incremental_revenue * 0.3  # Assuming 30% gross margin
                col1, col2, col3 = st.columns(3)
                col1.metric(label="Total Spend in 2023 (GBP)", value=f"£{total_spend/1e6:.2f}M")
                col2.metric(label="Incremental Revenue (GBP)", value=f"£{incremental_revenue/1e6:.2f}M")
                col3.metric(label="Incremental Gross Margin (GBP)", value=f"£{incremental_gross_margin/1e6:.2f}M")
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                
                # Ask user to enter total budget and channel spend constraints
                st.subheader("Optimization Inputs")
                budget_change_pct = st.number_input("Budget % Change", value=st.session_state.inputs.get("budget_change_pct", 0), key="budget_change_pct")
                total_budget = total_spend_df.loc[2023].sum() * (1 + budget_change_pct / 100)  
                
                min_spend = {}
                max_spend = {}
                
                cols = st.columns(3)
                #cols[0].markdown("### Channel")
                cols[0].markdown("### Min (%)")
                cols[1].markdown("### Max (%)")
                cols[2].markdown("### Last Year")
                
                for channel in media_channels:
                    col1, col2, col3 = st.columns(3)
                    # with col1:
                    #     col1.markdown(f"**{channel}**")
                    with col1:
                        min_spend[channel] = st.text_input(f"{channel}_Min", value=st.session_state.inputs.get(f"min_spend_{channel}", 0), key=f"min_spend_{channel}")
                    with col2:
                        max_spend[channel] = st.text_input(f"{channel}_Max", value=st.session_state.inputs.get(f"max_spend_{channel}", 0), key=f"max_spend_{channel}")
                    with col3:
                        col3.markdown(f"£{round(total_spend_df.loc[2023, channel]/1e6,1)}M")
    


                if st.button("Optimize Spend"):
                        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                        min_spend = {channel: total_spend_df.loc[2023, channel] * (1 + float(min_spend[channel]) / 100) for channel in media_channels if min_spend[channel]}
                        max_spend = {channel: total_spend_df.loc[2023, channel] * (1 + float(max_spend[channel]) / 100) for channel in media_channels if max_spend[channel]}
                        # min_spend = {k: float(v) for k, v in min_spend.items() if v}
                        # max_spend = {k: float(v) for k, v in max_spend.items() if v}
                        optimized_spend = optimize_media_spend(total_budget, media_channels, list(min_spend.values()), list(max_spend.values()), params)
                        if optimized_spend:
                            # Print the optimised metrics
                            new_total_spend = sum(optimized_spend.values())
                            new_incremental_revenue = calculate_incremental_revenue(optimized_spend, media_contr_df, params)
                            new_incremental_gross_margin = new_incremental_revenue * 0.3  # Assuming 30% gross margin
                            col1, col2, col3 = st.columns(3)
                            col1.metric(label="New Total Spend (GBP)", value=f"£{new_total_spend/1e6:.2f}M")
                            col2.metric(label="Optimised Incremental Revenue (GBP)", value=f"£{new_incremental_revenue/1e6:.2f}M")
                            col3.metric(label="Optimised Incremental Gross Margin (GBP)", value=f"£{new_incremental_gross_margin/1e6:.2f}M")
                            #st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                            #st.markdown('<div class="section-header">Optimized Total Spend</div>', unsafe_allow_html=True)                
                            
                            actual_spend = total_spend_df.loc[2023].to_dict()
                            col1, col2 = st.columns(2)
                            with col1:
                                opt_results_df = display_comparison_table(actual_spend, optimized_spend, media_contr_df, params)
                                st.dataframe(opt_results_df, height=320)
                                
                                # Display download button
                                opt_results_df_download = to_excel(opt_results_df)
                                b64 = base64.b64encode(opt_results_df_download).decode()
                                st.markdown(f"""
                                <a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="optimised_spend.xlsx">
                                    <i class="fas fa-download download-icon"></i>
                                </a>
                                """, unsafe_allow_html=True)
            
                                # Add download button for optimal spend
                                #st.markdown(generate_excel_download_link(opt_results_df, "optimal_spend", "Download"), unsafe_allow_html=True)
                                # st.markdown(
                                #     """
                                #     <div class="results-section">
                                #         <button class="download-btn">
                                #             <i class="fa fa-download"></i>
                                #         </button>
                                #     </div>
                                #     """,
                                #     unsafe_allow_html=True
                                # )
                                # Include Font Awesome for download icon
                                st.markdown(
                                    """
                                    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
                                    """,
                                    unsafe_allow_html=True
                                )
                            with col2:
                                display_optimized_spend_plot(optimized_spend)
                        
              # Custom CSS to push the logout button to the right and style it
               # Custom CSS to style the logout button and email display
                st.markdown("""
                <style>
                #root > div:nth-child(1) > div > div > div > div > section > div {padding-top: 2rem;}
                .logout-email-container {
                    position: fixed;
                    top: 3rem;  /* Increased from 0.5rem to move it lower */
                    right: 0.5rem;
                    z-index: 999999;
                    display: flex;
                    flex-direction: column;
                    align-items: flex-end;
                }
                .logout-button button {
                    background-color: #ff4b4b;
                    color: white;
                    border: none;
                    padding: 0.15rem 0.5rem;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 0.8rem;
                    margin: 2px 1px;
                    cursor: pointer;
                    border-radius: 3px;
                }
                .logout-button button:hover {
                    background-color: #ff0000;
                }
                .user-email {
                    font-size: 0.8rem;
                    margin-top: 0.25rem;
                    color: #888;
                }
                </style>
                """, unsafe_allow_html=True)
                
                # Create a container for the logout button and email
                logout_email_container = st.container()
                
                # Use the container to position the logout button and email
                with logout_email_container:
                    col1, col2 = st.columns([3, 1])
                    with col2:
                        st.markdown('<div class="logout-email-container">', unsafe_allow_html=True)
                        if st.session_state.get('access', False):
                            if st.button("Logout", key="logout_button"):
                                st.markdown("""
                                <meta http-equiv="refresh" content="0; url='https://mtflpjpww5ms3yv9galhh9.streamlit.app/'" />
                                """, unsafe_allow_html=True)
                            st.markdown(f'<div class="user-email">{st.session_state.get("user_email", "")}</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                                         

if __name__ == "__main__":
    main()
