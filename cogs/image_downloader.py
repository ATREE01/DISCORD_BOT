import discord
from discord.ext import commands
from discord import app_commands

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

import asyncio

import requests

import uuid
import os 

class ImageDownloader(commands.Cog, description="Use to download photo from website."):
    def __init__(self, bot):
        self.bot = bot
        self.service = Service(ChromeDriverManager().install())   
        self.chrome_options = self.init_chrome_option(Options())
    
    def init_chrome_option(self, options=Options):     
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--enable-unsafe-swiftshader")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument('--log-level=3')    
        return options
        
    @app_commands.command(name='download_img',description="download img from instagram or twitter")
    async def download_img(self, interaction: discord.Interaction, url:str):
        await interaction.response.defer()

        driver = webdriver.Chrome(service=self.service, options = self.chrome_options)
        try:
            if "instagram" in url:
                driver.get(url)
                await asyncio.sleep(4)
                img_urls = []
                post = driver.find_element(By.CLASS_NAME, "_aatk._aatn")
                try:
                    while True:
                        datas = post.find_elements(By.CLASS_NAME, "x5yr21d.xu96u03.x10l6tqk.x13vifvy.x87ps6o.xh8yej3") #找到所有的 注意這邊是find_elements 後面有s
                        for data in datas:
                            img_src = data.get_attribute('src')
                            if img_src not in img_urls: #如果這個連結之前沒有儲存過
                                img_urls.append(img_src)
                        button = driver.find_element(By.CLASS_NAME, "_afxw._al46._al47") #試著尋找有沒有button如果沒找地的話會跳exception 接下來就只會執行except的部分
                        button.click()#最重要的部分，去點擊那個向右的按鈕
                        await asyncio.sleep(0.3) #按下按鈕後給他時間讀取一下
                except:
                    pass
                    
                driver.close()
                
                for index, url in enumerate (img_urls):
                    response = requests.get(url)
                    if response.status_code:
                        filename = str(uuid.uuid4())
                        with open(f"{filename}.png",'wb') as output:
                            output.write(response.content)  
                            await interaction.followup.send(file = discord.File(f"{filename}.png"))
                        os.remove(f"{filename}.png")
                        
            elif 'twitter' or 'x' in url:
                driver.get(url)
                await asyncio.sleep(2)
                imgs = driver.find_elements(By.XPATH, "//img[@alt='圖片']")                
                for index, img in enumerate (imgs):
                    img_url = img.get_attribute('src')
                    response = requests.get(img_url)
                    if response.status_code:
                        filename = str(uuid.uuid4())
                        with open(f"{filename}.png",'wb') as output:
                            output.write(response.content)  
                            await interaction.followup.send(file = discord.File(f"{filename}.png")) 
                        os.remove(f"{filename}.png")
                driver.close()
        except Exception as e:
            # print(e)
            await interaction.followup.send("Incorrect URL!")

async def setup(bot):
    await bot.add_cog(ImageDownloader(bot))