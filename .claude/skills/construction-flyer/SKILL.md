---
name: construction-flyer
description: Nano Banana Pro automated flyer generator for All Elite Roofing & Siding. Uses reference flyers and real client job site photos from Google Drive to generate minimum 5 daily 4K flyers.
---

# Nano Banana Pro Flyer Generator

Automated flyer marketing system for All Elite Roofing & Siding.

## Recipe

1. **Logo**:
   - Location: `/Users/johnpineda/Documents/Projects/flyer-agent/all-elite/logo/logo.png`
   - Included clearly and prominently on every flyer.

2. **Reference Flyers**:
   - Library: `/Users/johnpineda/Documents/Projects/flyer-agent/reference-flyers/`
   - Magazine Covers: `reference_flyer16.jpg`, `reference_flyer17.jpg`, `reference_flyer18.jpeg`
   - Price & Value Comparison: `reference_flyer6.png`
   - Warning Signs / Inspection: `reference_flyer12.png`
   - Carousel Posts: `carousel-flyers/carousel1/` (6 sequential slides)

3. **Background Photography**:
   - Pulled dynamically from Google Drive:
     `/Users/johnpineda/Library/CloudStorage/GoogleDrive-engineeringwithjp@gmail.com/My Drive/NEDA Technologies/Clients/All Elite Construction`
   - Uses real drone and high-res job photos of finished roofs and siding.

4. **Company Information**:
   - **Company Name**: All Elite Roofing & Siding
   - **Legal Name**: All Elite Construction Corp NJ
   - **Website**: alleliteconstructioncorpnj.com
   - **Instagram**: @alleliteroofing (https://www.instagram.com/alleliteroofing/)
   - **Address**: 131 Main St STE 122, Hackensack, NJ 07601
   - **Phone**: (551) 335-9235
   - **Email**: info@alleliteconstructioncorpnj.com

5. **Direct Google Drive Delivery & Zero Local Disk Usage**:
   - Output destination:
     `/Users/johnpineda/Library/CloudStorage/GoogleDrive-engineeringwithjp@gmail.com/My Drive/NEDA Technologies/Client Flyers/Flyers/<YYYY>/<Month>/<MM-DD>/`
   - Shared Drive Link: https://drive.google.com/drive/folders/12Ho15EiJumnZkSAPm0I1Zd9Vwe6CuLiT?usp=sharing
   - No local files accumulate in Finder or output folders to save disk space.

6. **Daily Execution**:
   - Scheduled daily at 10:00 AM via macOS LaunchAgent (`com.nedatechnologies.flyer-generator.plist`).
   - Generates at least 5 flyers daily.
