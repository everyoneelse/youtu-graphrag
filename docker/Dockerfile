# 1. Use an official Python base image
FROM python:3.10

# 2. Install git for cloning the repository
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory
WORKDIR /youtu-graphrag

RUN git config --global user.email "siyuan@tencent.com"
RUN git config --global user.name "siyuan"

# 4. Clone the repository into the working directory
RUN git clone https://git.woa.com/siyuan_u/Youtu-GraphRAG-OpenSource

# 5. Install the 'uv' build tool globally
RUN pip install -r requirements.txt

# 6. Set the default command to start the example application
CMD ["python", "kt_rag.py"]
