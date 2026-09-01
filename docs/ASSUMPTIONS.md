# LPU Campus Digital Twin — Data Sources & Assumptions

## Verified Information ✅

| Item | Source | Verification |
|------|--------|-------------|
| Central Library is in Block 37 | Official LPU library page | ✅ Confirmed |
| Campus has Uni-Mall | LPU tour page (lpude.in/about-us/tour-lpu.php) | ✅ Confirmed |
| Campus has Uni-Hospital | LPU infrastructure descriptions | ✅ Confirmed |
| Campus has Uni-Polis | LPU infrastructure descriptions | ✅ Confirmed |
| Sports facilities exist | LPU infrastructure page lists multiple | ✅ Confirmed |
| Boys and Girls hostels exist | LPU residential info | ✅ Confirmed |
| Campus spans ~600 acres | LPU official materials | ✅ Confirmed |
| Multiple academic blocks exist | LPU campus tour and materials | ✅ Confirmed |
| Swimming pool exists | LPU sports facilities page | ✅ Confirmed |
| Indoor sports complex exists | LPU sports facilities page | ✅ Confirmed |

## Approximate Geometry ⚠️

| Item | Assumption | Replaceable? |
|------|-----------|-------------|
| Block dimensions (34-41) | Estimated from satellite imagery, 30-45m x 16-22m | ✅ Yes |
| Building heights | Estimated: 3-5 floors, 3m per floor | ✅ Yes |
| Road widths | Assumed 8m for main roads | ✅ Yes |
| Pathway widths | Assumed 3m for pedestrian paths | ✅ Yes |
| Building positions | Approximate relative placement | ✅ Yes |
| Campus simulation area | 200m x 200m representative subset of 600-acre campus | ✅ Yes |
| Parking capacities | Estimated | ✅ Yes |
| Hostel dimensions | Estimated 20m x 30m, 5 floors | ✅ Yes |
| Mall dimensions | Estimated 50m x 25m, 2 floors | ✅ Yes |
| Hospital dimensions | Estimated 35m x 25m, 4 floors | ✅ Yes |

## Not Yet Modeled (To Be Added) 📋

- Individual floor plans for any building
- Exact room layouts within blocks
- Precise entrance locations
- Elevator shaft positions
- Staircase positions
- Internal corridor geometry
- Exact road network from campus maps
- All campus gates (only Gate 1 and Gate 2 modeled)
- All hostel buildings (only one each for boys/girls)
- Exact tree and landscaping positions
- Amphitheatre and other event venues
- Administrative building
- Placement office

## Design Principle

> **When exact LPU campus information is unavailable, geometry and metadata are explicitly marked as `approximate` rather than presenting fabricated details as real.**
>
> All approximate geometry is **configurable and replaceable** — building dimensions, positions, and metadata can be updated in `campus_metadata.json` without code changes.

## Data Sources

1. **LPU Distance Education Tour Page**: https://www.lpude.in/about-us/tour-lpu.php
2. **LPU 360° Virtual Tour**: https://iviewd.com/lpu2/
3. **Google Maps Satellite View**: Approximate layout reference
4. **Official LPU Infrastructure Pages**: Building and facility descriptions
