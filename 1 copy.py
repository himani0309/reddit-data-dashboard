# streamlit_app.py

import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import ast

st.set_page_config(layout="wide")
st.title("📊 Reddit Posts Dashboard")

# Load and preprocess
df = pd.read_csv("Expanded_Fake_Reddit_Posts.csv")
for col in ['post_details'] + [f'comment_{i}_details' for i in range(1, 6)]:
    df[col] = df[col].apply(ast.literal_eval)

df['post_theme'] = df['post_details'].apply(lambda x: x[0])
df['post_misinfo'] = df['post_details'].apply(lambda x: x[1])
df['post_topic'] = df['post_details'].apply(lambda x: x[2])
df['post_date'] = pd.to_datetime(df['post_date'])
df['upvote_ratio'] = df['post_upvote'] / (df['post_upvote'] + df['post_downvote'])
df['post_month'] = df['post_date'].dt.to_period('M')

# Comment data
comment_themes, comment_misinfos = [], []
for i in range(1, 6):
    comment_themes += df[f'comment_{i}_details'].apply(lambda x: x[0]).tolist()
    comment_misinfos += df[f'comment_{i}_details'].apply(lambda x: x[1]).tolist()

comment_theme_df = pd.DataFrame({'theme': comment_themes})
comment_misinfo_df = pd.DataFrame({'misinfo': comment_misinfos})

# Aggregations
misinfo_df = pd.DataFrame({
    'Posts': df['post_misinfo'].value_counts(),
    'Comments': comment_misinfo_df['misinfo'].value_counts()
}).fillna(0)

monthly_trends = df.groupby(['post_month', 'post_theme']).size().unstack(fill_value=0)
monthly_trends.index = monthly_trends.index.to_timestamp()
topic_theme = df.groupby(['post_topic', 'post_theme']).size().unstack(fill_value=0)

# Chart: Post Theme Donut
st.subheader("1. Post Theme Distribution")
fig1, ax1 = plt.subplots()
ax1.pie(df['post_theme'].value_counts(), labels=df['post_theme'].value_counts().index,
        autopct='%1.1f%%', startangle=140, wedgeprops=dict(width=0.4))
ax1.axis('equal')
st.pyplot(fig1)

# Chart: Comment Theme Distribution
st.subheader("2. Comment Theme Distribution")
fig2, ax2 = plt.subplots()
sns.countplot(y='theme', data=comment_theme_df, order=comment_theme_df['theme'].value_counts().index, ax=ax2)
st.pyplot(fig2)

# Chart: Misinformation Bars
st.subheader("3. Misinformation in Posts vs Comments")
fig3, ax3 = plt.subplots()
misinfo_df.plot(kind='bar', ax=ax3)
st.pyplot(fig3)

# Chart: Topics Discussed
st.subheader("4. Topics Most Discussed in Posts")
fig4, ax4 = plt.subplots()
df['post_topic'].value_counts().sort_values().plot(kind='barh', ax=ax4, color='skyblue')
st.pyplot(fig4)

# Chart: Upvote Ratio by Theme
st.subheader("5. Upvote Ratio by Post Theme")
fig5, ax5 = plt.subplots()
sns.boxplot(x='post_theme', y='upvote_ratio', data=df, ax=ax5, palette="Set2")
st.pyplot(fig5)

# Chart: Upvote Ratio by Misinformation
st.subheader("6. Upvote Ratio by Misinformation Level")
fig6, ax6 = plt.subplots()
sns.boxplot(x='post_misinfo', y='upvote_ratio', data=df, ax=ax6, palette="Set3")
st.pyplot(fig6)

# Chart: Upvotes vs Downvotes
st.subheader("7. Upvotes vs Downvotes")
fig7, ax7 = plt.subplots()
sns.scatterplot(x='post_upvote', y='post_downvote', data=df, ax=ax7, alpha=0.6)
ax7.set_xscale("log")
ax7.set_yscale("log")
st.pyplot(fig7)

# Chart: Monthly Theme Trends
st.subheader("8. Monthly Theme Trends")
fig8, ax8 = plt.subplots()
monthly_trends.plot(ax=ax8, linewidth=2)
ax8.set_xlabel("Month")
ax8.set_ylabel("Post Count")
st.pyplot(fig8)

# Chart: Topic vs Theme Heatmap
st.subheader("9. Topic vs Theme Heatmap")
fig9, ax9 = plt.subplots(figsize=(10, 6))
sns.heatmap(topic_theme, annot=True, fmt='d', cmap="YlGnBu", ax=ax9)
st.pyplot(fig9)

# Chart: Comment Misinformation Count
st.subheader("10. Comment Misinformation Distribution")
fig10, ax10 = plt.subplots()
sns.countplot(x='misinfo', data=comment_misinfo_df, ax=ax10, palette="muted")
st.pyplot(fig10)



st.subheader("🔥 Most Controversial Posts (High Upvotes + Downvotes)")

df['controversy_score'] = df['post_upvote'] + df['post_downvote']
top_controversial = df.sort_values(by='controversy_score', ascending=False).head(10)

fig, ax = plt.subplots(figsize=(10, 6))
sns.barplot(y=top_controversial['post_title'], x=top_controversial['controversy_score'], ax=ax, palette="rocket")
ax.set_xlabel("Controversy Score (Upvotes + Downvotes)")
ax.set_ylabel("Post Title")
st.pyplot(fig)


st.subheader("🎭 Theme Alignment Between Post & Comments")

# Count how often post and comment themes match
alignment = []
for i in range(1, 6):
    match = df['post_theme'] == df[f'comment_{i}_details'].apply(lambda x: x[0])
    alignment.extend(match)

alignment_df = pd.Series(alignment).value_counts(normalize=True) * 100

fig, ax = plt.subplots()
alignment_df.plot(kind='bar', ax=ax, color=['green', 'red'])
ax.set_xticklabels(['Matched', 'Did Not Match'], rotation=0)
ax.set_ylabel("Percentage of Comments")
ax.set_title("How Often Do Comment Themes Match Post Theme?")
st.pyplot(fig)



st.subheader("📈 Misinformation Trend Over Time")

monthly_misinfo = df.groupby(['post_month', 'post_misinfo']).size().unstack().fillna(0)
monthly_misinfo.index = monthly_misinfo.index.to_timestamp()

fig, ax = plt.subplots(figsize=(12, 6))
monthly_misinfo.plot(ax=ax)
ax.set_title("Monthly Trend of Misinformation in Posts")
ax.set_xlabel("Month")
ax.set_ylabel("Number of Posts")
st.pyplot(fig)
