from shutil import copyfile

def your_awesome_function(raster, output_path, roi=False, algorithm='K-MEANS', variables=['MEAN', 'MODE'], debug=False):
    # Here you put your code
    copyfile(raster, output_path)
    return

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='An Awesome Script')
    parser.add_argument('raster', type=str, help='path to raster')
    parser.add_argument('output_path', type=str, help='path to use when saving the output')
    parser.add_argument('--roi', type=str, default=False, help='path to shapefile')
    parser.add_argument('--algorithm', type=str, default='K-MEANS', help='algorithm to use')
    parser.add_argument('--variables', type=str, nargs='+', default=['MEAN', 'MODE'], help='variables to use')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    # converts the parameters to a dictionary
    kwargs = vars(args)
    # this removes any parameter that has a None value, to use the default one specified in the function call
    kwargs = {k: kwargs[k] for k in kwargs if kwargs[k] is not None}
    your_awesome_function(**kwargs)

